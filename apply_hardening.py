#!/usr/bin/env python3
"""One-shot, idempotent hardening pass for Pegasus Phantom Menace.

Run from the repository root:

    python apply_hardening.py --dry-run      # show the plan, touch nothing
    python apply_hardening.py --yes          # do everything except build
    python apply_hardening.py --yes --build  # ... and rebuild + re-smoke

Every stage is independently idempotent and independently skippable
(--only/--skip take stage names). Patches assert their anchor exists, so a
drifted upstream file fails loudly rather than half-applying.

Never uses `git add -A`; stages explicit paths through GIT_INDEX_FILE.
"""
from __future__ import annotations

import argparse
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TMP = ROOT / ".pytest-tmp"
TMP.mkdir(exist_ok=True)
INDEX = str(ROOT / ".git" / "index2")
LOG = TMP / "apply_hardening.log"

BACKEND = ROOT / "pegasus" / "ui" / "web" / "backend"
C2DIR = ROOT / "pegasus" / "modules" / "c2"
WEB = ROOT / "pegasus" / "ui" / "web"

ENV = {
    **os.environ,
    "GIT_INDEX_FILE": INDEX,
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
    "CI": "1",
    "GIT_TERMINAL_PROMPT": "0",
}

DRY = False
ASSUME_YES = False
TOUCHED: list[str] = []


# ---------------------------------------------------------------- plumbing

def say(msg: str) -> None:
    print(msg, flush=True)


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}", flush=True)


def skip(msg: str) -> None:
    print(f"  [skip] {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"  [warn] {msg}", flush=True)


def die(msg: str) -> None:
    print(f"  [FAIL] {msg}", flush=True)
    raise SystemExit(1)


def run(cmd, cwd: Path = ROOT, timeout: int = 1800, check: bool = False):
    shown = " ".join(cmd) if isinstance(cmd, list) else cmd
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"\n$ ({cwd}) {shown}\n")
    if DRY:
        print(f"  [dry]  {shown}", flush=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    p = subprocess.run(
        cmd, cwd=cwd, env=ENV, shell=isinstance(cmd, str),
        capture_output=True, text=True, errors="replace", timeout=timeout,
    )
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(p.stdout or "")
        fh.write(p.stderr or "")
    if check and p.returncode != 0:
        die(f"command failed ({p.returncode}): {shown}\n{(p.stderr or p.stdout)[-800:]}")
    return p


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> bool:
    """Write only when content differs. Returns True when the file changed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    if not DRY:
        path.write_text(text, encoding="utf-8", newline="\n")
    TOUCHED.append(str(path.relative_to(ROOT)))
    return True


def patch(path: Path, pattern: str, repl: str, *, label: str,
          flags: int = re.M, count: int = 1) -> None:
    """Replace an anchored pattern, asserting the anchor is present."""
    if not path.exists():
        die(f"{path.relative_to(ROOT)} not found")
    text = read(path)
    m = re.search(pattern, text, flags)
    if not m:
        die(f"{label}: anchor not found in {path.relative_to(ROOT)}\n"
            f"       pattern: {pattern[:120]}")
    new = text[:m.start()] + re.sub(pattern, repl, text[m.start():m.end()], count=count, flags=flags) + text[m.end():]
    if new == text:
        skip(f"{label}: already applied")
        return
    if not DRY:
        path.write_text(new, encoding="utf-8", newline="\n")
    TOUCHED.append(str(path.relative_to(ROOT)))
    ok(label)


def verify_compiles(*paths: Path) -> None:
    if DRY:
        return
    for p in paths:
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as exc:
            die(f"generated file does not compile: {p}\n{exc}")


def local_addresses() -> set[str]:
    import socket
    addrs = {"127.0.0.1", "0.0.0.0", "::1", "::"}
    try:
        import psutil
        for _, entries in psutil.net_if_addrs().items():
            for entry in entries:
                addr = getattr(entry, "address", None)
                if addr:
                    addrs.add(addr.split("%")[0])
    except Exception:
        try:
            addrs.add(socket.gethostbyname(socket.gethostname()))
        except Exception:
            pass
    return addrs


# ---------------------------------------------------------------- stage: env

def stage_env() -> None:
    say("\n[1/16] environment")
    if not (ROOT / ".git").is_dir():
        die("not a git repository root")
    ok(f"GIT_INDEX_FILE={INDEX}")
    ok(f"PYTHONIOENCODING={ENV['PYTHONIOENCODING']}")
    if sys.version_info < (3, 11):
        warn(f"python {sys.version_info.major}.{sys.version_info.minor} < 3.11")
    if DRY:
        return
    TMP.mkdir(exist_ok=True)
    ok(f"log -> {LOG.relative_to(ROOT)}")


# ------------------------------------------------------ stage: c2 bind + TLS

C2_SERVER = '''"""Standalone C2 listener.

The listener follows the console's own posture: loopback unless the operator
opts into exposure. ``start()`` takes an explicit host so a caller can bind
deliberately, and ``PEGASUS_C2_TLS`` turns on TLS so ``wss://`` clients can
complete a handshake against this plain-HTTP-by-default server.
"""
import os
import threading

from flask import Flask, jsonify
from werkzeug.serving import ThreadedWSGIServer, make_server

from . import beacon_routes

_server: ThreadedWSGIServer | None = None
_BOUND_HOST: str | None = None


def c2_host() -> str:
    """Loopback unless the operator opts into network exposure."""
    return os.getenv("PEGASUS_C2_HOST", "127.0.0.1").strip() or "127.0.0.1"


def _ssl_context():
    """TLS for wss:// clients.

    unset/0 -> plain HTTP, 1/adhoc -> self-signed cert minted by werkzeug,
    any other value -> an explicit certfile, or ``certfile:keyfile``.
    """
    mode = os.getenv("PEGASUS_C2_TLS", "0").strip().lower()
    if mode in ("", "0", "false", "no", "off"):
        return None
    if mode in ("1", "true", "yes", "on", "adhoc"):
        return "adhoc"
    return mode


def start(port: int = 0, host: str | None = None) -> int:
    global _server, _BOUND_HOST
    host = host or c2_host()
    app = Flask("c2")
    ok = lambda data, code=200: (jsonify({"ok": True, "data": data}), code)  # noqa: E731
    fail = lambda err, code=400: (jsonify({"ok": False, "error": err}), code)  # noqa: E731
    beacon_routes.register(app, ok, fail)
    _server = make_server(host, port, app, threaded=True,
                          ssl_context=_ssl_context())
    _BOUND_HOST = host
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    return _server.server_port


def bound_host() -> str | None:
    return _BOUND_HOST


def tls_enabled() -> bool:
    return _ssl_context() is not None


def stop() -> None:
    global _server, _BOUND_HOST
    if _server:
        _server.shutdown()
        _server = None
        _BOUND_HOST = None
'''


def stage_c2_server() -> None:
    say("\n[2/16] c2/server.py — parametrised bind, loopback default, optional TLS")
    target = C2DIR / "server.py"
    if not target.exists():
        die("pegasus/modules/c2/server.py not found")
    write(target, C2_SERVER)
    verify_compiles(target)
    ok("bind host parametrised; PEGASUS_C2_TLS supported; bound_host()/tls_enabled() added")


def stage_app_host() -> None:
    say("\n[3/16] app.py — loopback default for PEGASUS_HOST")
    app = BACKEND / "app.py"
    text = read(app) if app.exists() else die("app.py not found")
    if '"PEGASUS_HOST", "127.0.0.1"' in text:
        skip("host() already defaults to loopback")
        return
    patch(
        app,
        r'def host\(\)\s*->\s*str:\s*(?:\n\s*)?return os\.getenv\("PEGASUS_HOST",\s*"0\.0\.0\.0"\)',
        'def host() -> str:\n'
        '    # Loopback by default: the console is a local single-operator tool and\n'
        '    # the docs say so. Set PEGASUS_HOST=0.0.0.0 to publish it.\n'
        '    return os.getenv("PEGASUS_HOST", "127.0.0.1").strip() or "127.0.0.1"',
        label="host() defaults to 127.0.0.1",
    )
    verify_compiles(app)


# -------------------------------------------------------- stage: c2_routes.py

C2_ROUTES = '''"""C2 console routes for the main web backend.

The console's Start/Stop/Kill buttons POST to /api/c2/*, but those routes only
ever existed on the separate access_workflow dashboard server, so every button
404'd against this app. The real listener already exists in
``pegasus.modules.c2.server``; this module exposes it to the console and reports
the port the listener actually bound rather than echoing the requested one.

Bind posture: loopback by default, matching the console. ``POST /api/c2/start``
accepts a ``host``, which is validated against the three wildcard/loopback
sentinels plus the host's own interface addresses, so a typo cannot produce an
unbindable listener. ``PEGASUS_C2_TLS`` enables TLS for ``wss://`` clients.
"""
from __future__ import annotations

import os
import socket
import time

from flask import request

_STATE: dict = {"running": False, "port": None, "host": None, "started_at": None,
                "autostarted": False}

_ALWAYS_OK = {"127.0.0.1", "0.0.0.0", "::1", "::"}


def _local_addresses() -> set[str]:
    addrs = set(_ALWAYS_OK)
    try:
        import psutil
        for _, entries in psutil.net_if_addrs().items():
            for entry in entries:
                addr = getattr(entry, "address", None)
                if addr:
                    addrs.add(str(addr).split("%")[0])
    except Exception:
        try:
            addrs.add(socket.gethostbyname(socket.gethostname()))
        except Exception:
            pass
    return addrs


def _resolve_host(value) -> str | None:
    """None means 'use the configured default'. Raises ValueError on a typo."""
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw in _local_addresses():
        return raw
    raise ValueError(
        "host %r is not a local interface address; use 127.0.0.1, 0.0.0.0, "
        "::1 or one of: %s" % (raw, ", ".join(sorted(_local_addresses())))
    )


def _uptime() -> str:
    if not _STATE["running"] or not _STATE["started_at"]:
        return "—"
    secs = int(time.time() - _STATE["started_at"])
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m{secs % 60:02d}s"
    return f"{secs // 3600}h{(secs % 3600) // 60:02d}m"


def _clients() -> int:
    """Number of DNA identities currently bound to a run."""
    try:
        from pegasus.modules.c2 import registry
        return len(registry._BY_DNA)
    except Exception:
        return 0


def start_listener(port: int, autostarted: bool = False,
                   host: str | None = None) -> dict:
    """Start the real C2 listener and record its bound port and host."""
    from pegasus.modules.c2 import server

    if _STATE["running"]:
        return {"started": True, "port": _STATE["port"], "host": _STATE["host"],
                "already_running": True, "uptime": _uptime(),
                "connected_clients": _clients(), "tls": server.tls_enabled()}
    bound_host = host or server.c2_host()
    bound = server.start(port, bound_host)
    _STATE.update(running=True, port=int(bound), host=bound_host,
                  started_at=time.time(), autostarted=autostarted)
    return {"started": True, "port": int(bound), "host": bound_host,
            "already_running": False, "uptime": _uptime(),
            "connected_clients": _clients(), "autostarted": autostarted,
            "tls": server.tls_enabled()}


def stop_listener() -> dict:
    from pegasus.modules.c2 import server

    was = _STATE["running"]
    if was:
        server.stop()
    _STATE.update(running=False, port=None, host=None, started_at=None,
                  autostarted=False)
    return {"stopped": bool(was), "was_running": bool(was)}


def maybe_autostart() -> dict | None:
    """Honour PEGASUS_C2_AUTOSTART so the listener comes up with the app.

    Called from start_server.py AFTER the main app is listening - starting a
    second WSGI listener inside create_app() stops the backend serving.
    """
    raw = os.environ.get("PEGASUS_C2_AUTOSTART", "1").strip().lower()
    if raw in ("0", "false", "no", "off", ""):
        return None
    try:
        port = int(os.environ.get("PEGASUS_C2_PORT", "8080"))
    except ValueError:
        port = 8080
    try:
        return start_listener(port, autostarted=True)
    except OSError as exc:
        # A busy or unbindable port must not take the whole console down.
        return {"started": False, "error": str(exc), "port": port}


def register(app, ok, fail):
    @app.get("/api/c2/status")
    def c2_status():
        from pegasus.modules.c2 import server
        return ok({
            "running": _STATE["running"],
            "port": _STATE["port"],
            "host": _STATE["host"],
            "bind_default": server.c2_host(),
            "tls": server.tls_enabled(),
            "uptime": _uptime(),
            "connected_clients": _clients(),
            "autostarted": _STATE["autostarted"],
            "autostart_enabled": os.environ.get(
                "PEGASUS_C2_AUTOSTART", "1").strip().lower()
                not in ("0", "false", "no", "off", ""),
        })

    @app.post("/api/c2/start")
    def c2_start():
        body = request.get_json(silent=True) or {}
        try:
            port = int(body.get("port") or os.environ.get("PEGASUS_C2_PORT") or 0)
        except (TypeError, ValueError):
            return fail("port must be numeric")
        if port < 0 or port > 65535:
            return fail("port out of range")
        try:
            host = _resolve_host(body.get("host"))
        except ValueError as exc:
            return fail(str(exc))
        try:
            return ok(start_listener(port, host=host))
        except OSError as exc:
            return fail(f"cannot bind C2 listener: {exc}", 500)

    @app.post("/api/c2/stop")
    def c2_stop():
        return ok(stop_listener())

    @app.post("/api/c2/kill")
    def c2_kill():
        """Queue a kill command for an implant and unbind its run.

        The command is delivered on the implant's next signed beacon; this does
        not reach out to the device directly. The console sends ``serial`` but
        the queue is keyed by DNA, so either identifier is accepted.
        """
        body = request.get_json(silent=True) or {}
        ident = str(body.get("dna") or body.get("serial") or "").strip()
        if not ident:
            return fail("dna or serial required")
        from pegasus.modules.c2 import queue, registry

        cid = queue.push(ident, "kill")
        run_id = registry.run_for(ident)
        if run_id:
            registry.unbind(run_id)
        return ok({"queued": True, "cid": cid, "identifier": ident,
                   "unbound_run": run_id,
                   "note": "delivered on the implant's next beacon"})

    @app.post("/api/c2/beacon")
    def c2_queue_command():
        """Queue an arbitrary command for an implant (operator-facing)."""
        body = request.get_json(silent=True) or {}
        ident = str(body.get("dna") or body.get("serial") or "").strip()
        command = str(body.get("command") or "").strip()
        if not ident:
            return fail("dna or serial required")
        if not command:
            return fail("command required")
        from pegasus.modules.c2 import queue

        return ok({"queued": True, "cid": queue.push(ident, command),
                   "identifier": ident})
'''


def stage_c2_routes() -> None:
    say("\n[4/16] c2_routes.py — accept and report host, validate it, TLS state")
    target = BACKEND / "c2_routes.py"
    if not target.exists():
        die("c2_routes.py not found")
    if "_resolve_host" in read(target):
        skip("c2_routes.py already carries host handling")
        return
    write(target, C2_ROUTES)
    verify_compiles(target)
    ok("host accepted + validated; status reports bind_default/tls; state carries host")


def stage_start_server() -> None:
    say("\n[5/16] start_server.py — autostart after the app is listening")
    target = ROOT / "start_server.py"
    if not target.exists():
        warn("start_server.py not found - skipping")
        return
    text = read(target)
    if "c2_routes.maybe_autostart" in text:
        skip("autostart already wired")
        return

    block = textwrap.dedent('''
        # C2 autostart. Deliberately NOT inside create_app(): starting a second
        # WSGI listener while the first app is still being constructed stops the
        # backend serving. This runs once the socket is already listening.
        try:
            from pegasus.ui.web.backend import c2_routes as _c2_routes
            _c2_routes.maybe_autostart()
        except Exception as _exc:  # autostart must never take the console down
            print(f"C2 autostart skipped: {_exc}")
    ''')

    lines = text.splitlines(keepends=True)
    markers = (r"\.join\(", r"serve_forever\(", r"while True:")
    chosen = None
    for pattern in markers:
        for i, line in enumerate(lines):
            if re.search(pattern, line):
                chosen = i
                break
        if chosen is not None:
            break
    if chosen is None:
        for i, line in enumerate(lines):
            if re.match(r"if __name__", line):
                chosen = i
                break
    if chosen is None:
        chosen = len(lines)
        warn("no join/serve_forever/__main__ marker - appending at end of file")

    indent = re.match(r"\s*", lines[chosen]).group(0) if chosen < len(lines) else ""
    block = textwrap.indent(block.strip("\n"), indent) + "\n\n"
    lines.insert(chosen, block)
    if not DRY:
        target.write_text("".join(lines), encoding="utf-8", newline="\n")
    TOUCHED.append("start_server.py")
    verify_compiles(target)
    ok(f"autostart inserted before line {chosen + 1}")


# ------------------------------------------------------------- stage: ignore

def stage_gitignore() -> None:
    say("\n[6/16] .gitignore — un-ignore build-required accent.ts")
    gi = ROOT / ".gitignore"
    text = read(gi) if gi.exists() else ""
    if "!pegasus/ui/web/src/lib/accent.ts" in text:
        skip("accent.ts un-ignore already present")
        return
    text = text.rstrip("\n") + (
        "\n\n# accent.ts is build-required source, not a build artefact\n"
        "!pegasus/ui/web/src/lib/accent.ts\n"
    )
    write(gi, text)
    ok("un-ignore rule appended")


def stage_accent() -> None:
    say("\n[7/16] accent.ts — diagnose, then force-add")
    target = WEB / "src" / "lib" / "accent.ts"
    if not target.exists():
        warn("accent.ts does not exist on disk - check the path")
        return
    p = run(["git", "check-ignore", "-v", str(target.relative_to(ROOT))])
    if p.returncode == 0 and p.stdout.strip():
        warn(f"ignored by: {p.stdout.strip()}")
    else:
        ok("not currently matched by any ignore rule")
    run(["git", "add", "-f", str(target.relative_to(ROOT))], check=False)
    ok("force-added to the index")


def stage_dist() -> None:
    say("\n[8/16] dist/ — untrack, keep on disk")
    p = run(["git", "ls-files", "dist"])
    if not (p.stdout or "").strip():
        skip("dist/ already untracked")
        return
    tracked = [line for line in p.stdout.splitlines() if line.strip()]
    warn(f"{len(tracked)} tracked path(s): {', '.join(tracked[:4])}")
    run(["git", "rm", "-r", "--cached", "--quiet", "dist"], check=False)
    run(["git", "add", ".gitignore"], check=False)
    ok("untracked; files remain on disk and in history")


# ---------------------------------------------------------- stage: gui-demo

def stage_gui_demo() -> None:
    say("\n[9/16] gui-demo.html — drop the third logo, fold the fourth colour")
    target = ROOT / "gui-demo.html"
    if not target.exists():
        warn("gui-demo.html not found - skipping")
        return
    text = read(target)
    original = text

    # 1. Fold the demo's private --signal token onto the app signal.
    text = text.replace("#ff5a1f", "#ff3d00").replace("#FF5A1F", "#FF3D00")

    # 2. Replace the inline bolt data-URI with the real desktop icon.
    lines = text.splitlines(keepends=True)
    icon = "electron/build/icon.png"
    changed_line = False
    for i, line in enumerate(lines):
        if i > 40 and changed_line:
            break
        # leave the <link rel="icon"> added by 5648014 alone
        if "rel=\"icon\"" in line or "rel='icon'" in line:
            continue
        m = re.search(r'(src|href)=("|\')data:image/[a-z+]+;base64,[A-Za-z0-9+/=]+(\2)', line)
        if m:
            lines[i] = line[:m.start()] + f'src="{icon}"' + line[m.end():]
            changed_line = True
            break
    if changed_line:
        text = "".join(lines)
        ok(f"inline bolt data-URI -> {icon}")
    else:
        warn("no inline base64 logo found outside the favicon link")

    if text == original:
        skip("gui-demo.html unchanged")
        return
    write(target, text)
    ok("third logo and fourth brand colour resolved")


# ------------------------------------------------------ stage: submodule

def stage_memory_primitives() -> None:
    say("\n[10/16] MemoryPrimitives — commit nested working tree, bump gitlink")
    nested = ROOT / "agents" / "specialized" / "MemoryPrimitives"
    if not (nested / ".git").exists():
        warn("no nested .git - skipping (nothing to preserve)")
        return
    p = run(["git", "-C", str(nested), "status", "--porcelain"])
    if not (p.stdout or "").strip():
        skip("nested tree already clean")
    else:
        run(["git", "-C", str(nested), "add", "--", "."], check=False)
        run(["git", "-C", str(nested), "commit", "-m",
             "MemoryPrimitives: commit the working-tree changes that exist only on this host"],
            check=False)
        ok("nested changes committed")
    run(["git", "add", "agents/specialized/MemoryPrimitives"], check=False)
    ok("parent gitlink staged")


# ---------------------------------------------------------- stage: dependabot

DEPENDABOT = '''version: 2
updates:
  - package-ecosystem: npm
    directory: /electron
    schedule: { interval: weekly }
    open-pull-requests-limit: 5
    groups:
      electron-devtooling:
        patterns: ["*"]
        exclude-patterns: ["electron"]
    ignore:
      # 2 unpatched alerts, no fixed release exists. See docs/PLAN.md #73.
      - dependency-name: extract-zip
      # 88 alerts, all cleared only at >=42.11.16; a major migration, tracked
      # separately rather than drip-fed by Dependabot.
      - dependency-name: electron
  - package-ecosystem: npm
    directory: /packages/pegasus-desktop
    schedule: { interval: weekly }
    ignore:
      - dependency-name: electron
  - package-ecosystem: npm
    directory: /pegasus/ui/web
    schedule: { interval: weekly }
  - package-ecosystem: pip
    directory: /pegasus
    schedule: { interval: weekly }
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: monthly }
# Deliberately no entry for weapons/: 396 of the 497 alerts live there and each
# needs a vendoring decision, not a bot PR.
'''


def stage_dependabot() -> None:
    say("\n[11/16] .github/dependabot.yml")
    target = ROOT / ".github" / "dependabot.yml"
    if write(target, DEPENDABOT):
        ok("created (this switches Dependabot updates on repo-wide)")
    else:
        skip("already present")


# --------------------------------------------------------------- stage: docs

SECURITY_MD = '''# Security posture

## Bind addresses

| Variable | Default | Meaning |
|---|---|---|
| `PEGASUS_HOST` | `127.0.0.1` | Console bind. Loopback: the console is a local single-operator tool. Set `0.0.0.0` to publish it. |
| `PEGASUS_C2_HOST` | `127.0.0.1` | C2 listener bind. Follows the console posture; `POST /api/c2/start` accepts a `host` validated against loopback, the wildcards and the host's own interface addresses. |
| `PEGASUS_C2_TLS` | `0` | `0` plain HTTP, `1`/`adhoc` self-signed, anything else an explicit `certfile` or `certfile:keyfile`. |

`POST /api/c2/start` refuses a host that is neither `127.0.0.1`, `0.0.0.0`,
`::1`, `::` nor a local interface address, so a typo cannot produce a listener
nobody can reach.

## Operator gate

`PEGASUS_REQUIRE_AUTH` is **opt-in**. Unset (default) the console runs
unauthenticated as a local tool and `operator.current()` returns the local
identity. Set it and every route needs a token or session, and the CSRF check
applies to writes. Publishing the console on `0.0.0.0` without setting this flag
publishes it unauthenticated.

## Token rotation

The live `ghp_` PAT is redundant: tooling authenticates through the Windows
credential manager (`gh auth setup-git`, `credential.helper=manager`) with a
keyring `gho_` token. Revoke the PAT at GitHub → Settings → Developer settings →
Personal access tokens. No literal remains in any tracked file, but it was
exposed for the length of the engagement.

## extract-zip

Two Dependabot alerts, no upstream fix, ignored in `.github/dependabot.yml`.

- **Where:** build-time only, a transitive dependency of `electron-builder`'s
  unpack path. Not shipped inside the installer, so not reachable at runtime.
- **Exposure:** a malicious archive processed during `npm run dist:win`.
- **Mitigation:** build from tagged trees only, and pre-inspect any third-party
  `.zip` before it reaches the build. Revisit when upstream patches.

## Vendored tree

`weapons/` carries 396 of the 497 advisories including all 16 criticals. It is
226 tracked files of third-party `strix-agent 0.8.3`, not a submodule, so each
one needs a vendoring decision. There is no Dependabot entry for it by design.

## Known gaps

- The C2 kill command lands on the implant's next signed beacon. It does not
  reach out to the device.
- BB84 QKD is a classical-RNG simulation. Lamport OTS is single-message.
- The token ledger is local JSON accounting, not a chain.
'''

C2_MD = '''# C2 listener

## Bind

Loopback by default (`PEGASUS_C2_HOST=127.0.0.1`), matching the console. The
listener is started from the console or by autostart, and the response reports
the port and host it **actually** bound, never an echo of the request.

```
POST /api/c2/start   {"port": 8098, "host": "0.0.0.0"}
```

`host` is validated against `127.0.0.1`, `0.0.0.0`, `::1`, `::` and the host's
own interface addresses. Anything else is a 400 that lists the valid choices.

## TLS

`wss://` clients need TLS. Set `PEGASUS_C2_TLS=1` for a self-signed certificate,
or point it at an explicit `certfile` / `certfile:keyfile`. `GET /api/c2/status`
reports the live `tls` state so the console can show whether `ws://` or `wss://`
is correct. `adhoc` requires `cryptography`, which is pinned in
`requirements.txt`.

## Autostart

`PEGASUS_C2_AUTOSTART` (default on) is honoured by `maybe_autostart()`, which
`start_server.py` calls **after** the app socket is listening. It is not called
from `create_app()`: starting a second WSGI listener while the first app is
still being constructed stops the backend serving.

`PEGASUS_C2_PORT` sets the autostart port (default 8080). A busy port returns
`{"started": false, "error": ...}` and never takes the console down.

## Kill semantics — the honest limit

```
POST /api/c2/kill {"dna": "..."}   (or {"serial": "..."})
```

The kill command is pushed to the queue and the run is unbound from the
registry. It is **delivered on the implant's next signed beacon**. The listener
does not reach out to the device, so a kill is not instant and an offline
implant keeps running until it next checks in. The response says so rather than
implying immediate termination.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/c2/status` | running, port, host, bind_default, tls, uptime, bound DNA count, autostart state |
| POST | `/api/c2/start` | start; returns the actually-bound port and host |
| POST | `/api/c2/stop` | stop |
| POST | `/api/c2/kill` | queue kill + unbind run |
| POST | `/api/c2/beacon` | queue an arbitrary command |
'''

HANDOFF_73 = '''
## 73. HANDOFF

Project: Pegasus Phantom Menace v2.3.4 / bind posture, autostart, packaging hygiene and the green-build gates
Status: hardening applied - the C2 listener is loopback by default with an explicit validated override and optional TLS, autostart is wired in the only place it is safe, and the packaging and CI blockers are closed
Features: `c2.server.start()` takes a host and defaults it to loopback via `c2_host()`, matching the console posture recorded in handoffs 70 and 71; `PEGASUS_C2_TLS` mints an adhoc certificate or accepts an explicit certfile so `wss://` clients complete a handshake instead of failing it; `POST /api/c2/start` accepts a `host` validated against the loopback and wildcard sentinels plus the host's own interface addresses, so a typo cannot produce an unbindable listener; `maybe_autostart()` is invoked from `start_server.py` after the app socket is listening, which is the only safe place because starting a second WSGI listener inside `create_app()` stops the backend serving; `app.py` `host()` defaults `PEGASUS_HOST` to `127.0.0.1`; `accent.ts` is un-ignored and force-added; `dist/` is untracked with the files left on disk; the third logo in `gui-demo.html` is replaced with the desktop icon and its private `--signal` colour is folded onto the brand signal; the MemoryPrimitives working tree is committed inside the nested repository and the parent gitlink is bumped; `.github/dependabot.yml` exists with the `extract-zip` and `electron` ignores and no `weapons/` entry; `docs/SECURITY.md` and `docs/C2.md` record the posture
Log: log/events.jsonl
Release: v2.3.4 pending - blocked on the frontend rebuild and the smoke
Push blocked: none
Next: rebuild the web bundle, read the new hashes out of dist/index.html, update EXPECT_BUNDLE in the smoke script, run it to PACKAGED_233_OK then INSTALL_SMOKE_OK, bump every version surface to 2.3.4, retag, republish
Author: Trey A. Smith | Authenticated, Inc. | @projectzerodays
Notes: the `extract-zip` mitigation, recorded here because the ignore above is only honest if the risk is written down. It is a build-time-only transitive dependency of electron-builder's unpack path and is not shipped inside the installer, so it is unreachable at runtime; the exposure is a malicious archive processed during `npm run dist:win`. Mitigations are to build from tagged trees only and to pre-inspect any third-party `.zip` before it reaches the build, and the alert is ignored in `.github/dependabot.yml` until upstream patches. Honest caveats - the bind change alters the posture of two surfaces at once, so both are recorded in `docs/SECURITY.md` rather than left implicit, and publishing the console on `0.0.0.0` without `PEGASUS_REQUIRE_AUTH` publishes it unauthenticated; the kill command still only lands on the implant's next signed beacon; the 497 advisories are still open, now with a config that lets the first-party ones be worked without `weapons/` failing every run; and the GitHub PAT still has to be revoked on the GitHub side.
'''

REVIEW_CHECKLIST = '''# Review checklist

## Route registration

Any route module added under `pegasus/ui/web/backend/` **must** have its
`register()` call in `create_app()`. Four modules were once written and never
registered, and that alone was the whole of the 30 HTTP failures in handoff 70.

`pegasus/tests/test_route_registration.py` enforces it - run it before review.

## Security posture

- [ ] New bind or listen surface documented in `docs/SECURITY.md`
- [ ] New write route behind the `confirm=true` gate if it changes system state
- [ ] No credential written into a tracked file
- [ ] Path parameters traversal-guarded

## Packaging

- [ ] `EXPECT_BUNDLE` updated if the bundle hashes moved
- [ ] Smoke run to `PACKAGED_233_OK` then `INSTALL_SMOKE_OK`
- [ ] No generated artefact staged; `dist/` stays untracked

## Honesty

- [ ] Limits of the feature recorded, not implied away
- [ ] A handoff written into `docs/PLAN.md`, never `docs/HANDOFF.md`
'''


def stage_docs() -> None:
    say("\n[12/16] docs — SECURITY.md, C2.md, PLAN handoff 73, review checklist")
    for rel, body in (("docs/SECURITY.md", SECURITY_MD),
                      ("docs/C2.md", C2_MD),
                      ("docs/REVIEW_CHECKLIST.md", REVIEW_CHECKLIST)):
        if write(ROOT / rel, body):
            ok(rel)
        else:
            skip(f"{rel} unchanged")

    plan = ROOT / "docs" / "PLAN.md"
    if not plan.exists():
        warn("docs/PLAN.md not found - handoff not written")
        return
    text = read(plan)
    if "## 73. HANDOFF" in text:
        skip("handoff 73 already present")
        return
    write(plan, text.rstrip("\n") + "\n" + HANDOFF_73)
    ok("handoff 73 appended to PLAN.md (HANDOFF.md is generated - do not hand-edit)")


# ----------------------------------------------------------------- stage: CI

CI_YML = '''name: ci

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: install
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest ruff pip-audit
      - name: ruff
        run: ruff check pegasus scripts --select E9,F63,F7,F82 --output-format concise
      - name: py_compile sweep
        run: python -m compileall -q pegasus scripts
      - name: pytest
        env:
          PYTHONIOENCODING: utf-8
        run: python -m pytest pegasus/tests -q --import-mode=importlib
      - name: boot + route-duplicate probe
        env:
          PEGASUS_REQUIRE_AUTH: "0"
        run: python scripts/route_probe.py
      # Advisory while the 497 open advisories are worked down. Flip to
      # blocking once the first-party manifests are clean.
      - name: pip-audit (advisory)
        continue-on-error: true
        run: pip-audit -r requirements.txt

  node:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - name: install
        working-directory: pegasus/ui/web
        run: npm ci --foreground-scripts
      - name: typecheck
        working-directory: pegasus/ui/web
        run: npm run typecheck
      - name: build
        working-directory: pegasus/ui/web
        run: npm run build
      # First-party manifests only: weapons/ would fail the job every run.
      - name: npm audit (first party, high and above)
        working-directory: pegasus/ui/web
        run: npm audit --audit-level=high
'''

ROUTE_PROBE = '''#!/usr/bin/env python3
"""Boot create_app, assert it serves and that no route is registered twice."""
from __future__ import annotations

import json
import sys

from pegasus.ui.web.backend.app import create_app


def main() -> int:
    app = create_app()
    rules = [(r.rule, ",".join(sorted(r.methods - {"HEAD", "OPTIONS"})))
             for r in app.url_map.iter_rules()]
    dupes = sorted({k for k in rules if rules.count(k) > 1})
    client = app.test_client()
    health = client.get("/api/health")
    print(json.dumps({"routes": len(rules), "duplicates": dupes,
                      "health": health.status_code}))
    if health.status_code != 200:
        print("health probe failed", file=sys.stderr)
        return 1
    if dupes:
        print(f"{len(dupes)} duplicate route(s): {dupes[:6]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def stage_ci() -> None:
    say("\n[13/16] CI — green gates, first-party-only audit")
    if write(ROOT / ".github" / "workflows" / "ci.yml", CI_YML):
        ok(".github/workflows/ci.yml rewritten")
    else:
        skip("ci.yml unchanged")
    if write(ROOT / "scripts" / "route_probe.py", ROUTE_PROBE):
        verify_compiles(ROOT / "scripts" / "route_probe.py")
        ok("scripts/route_probe.py created (boot + duplicate-route gate)")
    else:
        skip("route_probe.py unchanged")


# -------------------------------------------------------------- stage: tests

TEST_C2 = '''"""Contract tests for the console-facing C2 routes."""
from __future__ import annotations

import pytest

from pegasus.ui.web.backend.app import create_app
from pegasus.ui.web.backend import c2_routes


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_status_reports_bind_default_and_tls(client):
    data = client.get("/api/c2/status").get_json()["data"]
    assert data["running"] is False
    assert data["bind_default"] in ("127.0.0.1", "::1")
    assert "tls" in data


def test_start_rejects_non_numeric_port(client):
    r = client.post("/api/c2/start", json={"port": "http"})
    assert r.status_code == 400
    assert "numeric" in r.get_json()["error"]


def test_start_rejects_out_of_range_port(client):
    assert client.post("/api/c2/start", json={"port": 70000}).status_code == 400


def test_start_rejects_remote_host(client):
    r = client.post("/api/c2/start", json={"port": 0, "host": "203.0.113.9"})
    assert r.status_code == 400
    assert "not a local interface address" in r.get_json()["error"]


def test_start_accepts_loopback_and_reports_bound_port(client):
    body = client.post("/api/c2/start", json={"port": 0, "host": "127.0.0.1"}).get_json()["data"]
    try:
        assert body["started"] is True
        assert body["host"] == "127.0.0.1"
        assert isinstance(body["port"], int) and body["port"] > 0
    finally:
        client.post("/api/c2/stop")


def test_kill_requires_an_identifier(client):
    r = client.post("/api/c2/kill", json={})
    assert r.status_code == 400
    assert "dna or serial" in r.get_json()["error"]


def test_kill_states_the_delivery_limit(client):
    body = client.post("/api/c2/kill", json={"dna": "d" * 16}).get_json()["data"]
    assert body["queued"] is True
    assert "next beacon" in body["note"]


def test_beacon_requires_command(client):
    r = client.post("/api/c2/beacon", json={"dna": "d" * 16})
    assert r.status_code == 400
    assert "command required" in r.get_json()["error"]


def test_resolve_host_rejects_a_typo():
    with pytest.raises(ValueError):
        c2_routes._resolve_host("999.999.999.999")


def test_resolve_host_passes_sentinels():
    for sentinel in ("127.0.0.1", "0.0.0.0", "::1"):
        assert c2_routes._resolve_host(sentinel) == sentinel
    assert c2_routes._resolve_host("") is None
'''

TEST_REG = '''"""Every route module under the backend must be registered in create_app().

Four modules were once written and never registered; the console called their
paths and got 404s. This makes that failure mode a test failure.
"""
from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "ui" / "web" / "backend"
EXEMPT = {"__init__.py", "app.py"}


def _modules_with_register():
    for path in BACKEND.glob("*_routes.py"):
        if path.name in EXEMPT:
            continue
        if re.search(r"^def register\(", path.read_text(encoding="utf-8"), re.M):
            yield path.name[:-3]


def test_every_route_module_is_registered():
    app_src = (BACKEND / "app.py").read_text(encoding="utf-8")
    missing = [m for m in _modules_with_register()
               if f"{m}.register(" not in app_src
               and f"{m}.register(app" not in app_src]
    assert not missing, f"route module(s) defined but never registered: {missing}"
'''


def stage_tests() -> None:
    say("\n[14/16] contract tests for the new routes + a registration guard")
    tests = ROOT / "pegasus" / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    for name, body in (("test_c2_routes_contract.py", TEST_C2),
                       ("test_route_registration.py", TEST_REG)):
        target = tests / name
        if write(target, body):
            verify_compiles(target)
            ok(f"pegasus/tests/{name}")
        else:
            skip(f"{name} unchanged")


# ------------------------------------------------------- stage: node_modules

def stage_node_modules() -> None:
    say("\n[15/16] node_modules repair + EALLOWSCRIPTS")
    if os.name != "nt":
        warn("non-Windows: run the npm steps by hand")
        return

    for proc in ("node", "electron", "esbuild"):
        run(["powershell", "-NoProfile", "-Command",
             f"Get-Process {proc} -ErrorAction SilentlyContinue | Stop-Process -Force"])

    for rel in ("electron/node_modules", "pegasus/ui/web/node_modules",
                "packages/pegasus-desktop/node_modules"):
        target = ROOT / rel
        if target.exists():
            if DRY:
                print(f"  [dry]  rmdir {rel}", flush=True)
            else:
                shutil.rmtree(target, ignore_errors=True)
            TOUCHED.append(rel)
            ok(f"removed {rel}")

    run(["npm.cmd", "cache", "verify"], timeout=600)

    version = run(["npm.cmd", "--version"]).stdout.strip()
    ok(f"npm {version}")

    # EALLOWSCRIPTS: npm gates install scripts. electron, esbuild and
    # electron-builder all need postinstall, so this is not an --ignore-scripts
    # case. Prefer the config key, then the flag, then the manual path.
    attempts = [
        (["npm.cmd", "config", "set", "allow-scripts", "true", "--location", "project"],
         "config allow-scripts"),
        (["npm.cmd", "ci", "--allow-scripts", "--foreground-scripts"], "ci --allow-scripts"),
        (["npm.cmd", "ci", "--foreground-scripts"], "ci --foreground-scripts"),
    ]
    installed = False
    for cmd, label in attempts:
        p = run(cmd, cwd=ROOT / "electron", timeout=1800)
        if p.returncode == 0 and not re.search(r"EALLOWSCRIPTS", p.stderr or ""):
            ok(f"installed via {label}")
            installed = True
            break
        warn(f"{label} failed: {(p.stderr or '').strip().splitlines()[-1][:160]}")

    if not installed:
        warn("falling back to --ignore-scripts plus manual postinstall")
        run(["npm.cmd", "ci", "--ignore-scripts"], cwd=ROOT / "electron", timeout=1800)
        for script in ("electron/install.js", "esbuild/install.js"):
            path = ROOT / "electron" / "node_modules" / script
            if path.exists():
                run(["node", str(path)], cwd=ROOT / "electron", timeout=900)
                ok(f"ran {script}")

    probe = run(["node", "-e", "console.log(require('electron'))"], cwd=ROOT / "electron")
    if probe.returncode == 0:
        ok(f"electron resolves: {probe.stdout.strip()[:70]}")
    else:
        warn("electron still does not resolve - check the EALLOWSCRIPTS path above")

    for rel in ("pegasus/ui/web", "packages/pegasus-desktop"):
        run(["npm.cmd", "ci", "--foreground-scripts"], cwd=ROOT / rel, timeout=1800)


# ------------------------------------------------------------ stage: build

def stage_build() -> None:
    say("\n[16/16] rebuild, EXPECT_BUNDLE, smoke")
    if not ASSUME_YES:
        say("  build is long - pass --yes --build to run it")
        return

    p = run(["npm.cmd", "run", "build"], cwd=WEB, timeout=1800)
    if p.returncode != 0:
        die(f"build failed:\n{(p.stderr or p.stdout)[-1200:]}")
    ok("bundle built")

    # vite does not exit; kill node by image name afterwards
    run(["powershell", "-NoProfile", "-Command",
         "Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force"])

    index = WEB / "dist" / "index.html"
    if not index.exists():
        die("dist/index.html missing after build")
    html = read(index)
    js = re.search(r"assets/(index-[A-Za-z0-9_-]+\.js)", html)
    css = re.search(r"assets/(index-[A-Za-z0-9_-]+\.css)", html)
    if not (js and css):
        die("could not read the bundle hashes out of dist/index.html")
    bundle = [f"assets/{js.group(1)}", f"assets/{css.group(1)}"]
    ok(f"bundle: {', '.join(bundle)}")

    smoke = TMP / "smoke_233.py"
    if not smoke.exists():
        warn(f"{smoke.relative_to(ROOT)} not present - patch EXPECT_BUNDLE by hand")
    else:
        text = read(smoke)
        new, n = re.subn(r"EXPECT_BUNDLE\s*=\s*\[[^\]]*\]",
                         "EXPECT_BUNDLE = " + json.dumps(bundle), text, flags=re.S)
        if n == 0:
            warn("no EXPECT_BUNDLE assignment found")
        else:
            write(smoke, new)
            ok("EXPECT_BUNDLE updated")
            p = run([sys.executable, str(smoke)], timeout=3600)
            tail = (p.stdout or "") + (p.stderr or "")
            if "INSTALL_SMOKE_OK" in tail:
                ok("INSTALL_SMOKE_OK")
            elif "PACKAGED_233_OK" in tail:
                warn("PACKAGED_233_OK but no INSTALL_SMOKE_OK - read the log")
            else:
                warn(f"smoke did not reach a green marker - see {LOG.relative_to(ROOT)}")


# ------------------------------------------------------------------ stage: git

STAGE_PATHS = [
    "pegasus/modules/c2/server.py",
    "pegasus/ui/web/backend/c2_routes.py",
    "pegasus/ui/web/backend/app.py",
    "start_server.py",
    ".gitignore",
    "gui-demo.html",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    "docs/SECURITY.md",
    "docs/C2.md",
    "docs/REVIEW_CHECKLIST.md",
    "docs/PLAN.md",
    "scripts/route_probe.py",
    "pegasus/tests/test_c2_routes_contract.py",
    "pegasus/tests/test_route_registration.py",
    "agents/specialized/MemoryPrimitives",
]


def stage_git(commit: bool) -> None:
    say("\n[git] stage explicit paths (never -A)")
    for rel in STAGE_PATHS:
        if (ROOT / rel).exists():
            run(["git", "add", "--", rel], check=False)
    if DRY:
        return
    p = run(["git", "status", "--porcelain"])
    print(p.stdout.rstrip() or "  (nothing staged)")
    if commit and p.stdout.strip():
        run(["git", "commit", "-m",
             "harden: loopback C2 bind with validated override and TLS, safe autostart, "
             "packaging hygiene, docs, CI gates and route-registration tests"],
            check=False)
        ok("committed")


# --------------------------------------------------------------------- main

STAGES = {
    "env": stage_env,
    "c2_server": stage_c2_server,
    "app_host": stage_app_host,
    "c2_routes": stage_c2_routes,
    "start_server": stage_start_server,
    "gitignore": stage_gitignore,
    "accent": stage_accent,
    "dist": stage_dist,
    "gui_demo": stage_gui_demo,
    "memory_primitives": stage_memory_primitives,
    "dependabot": stage_dependabot,
    "docs": stage_docs,
    "ci": stage_ci,
    "tests": stage_tests,
    "node_modules": stage_node_modules,
    "build": stage_build,
}

ORDER = list(STAGES)


def main() -> int:
    global DRY, ASSUME_YES
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="show the plan, touch nothing")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ap.add_argument("--build", action="store_true", help="rebuild, patch EXPECT_BUNDLE, smoke")
    ap.add_argument("--commit", action="store_true", help="commit the staged paths")
    ap.add_argument("--only", nargs="*", choices=ORDER, help="run only these stages")
    ap.add_argument("--skip", nargs="*", choices=ORDER, default=[], help="skip these stages")
    args = ap.parse_args()

    DRY, ASSUME_YES = args.dry_run, args.yes

    plan = [s for s in (args.only or ORDER) if s not in args.skip]
    if not args.build and "build" in plan:
        plan.remove("build")

    say(f"repo   {ROOT}")
    say(f"stages {', '.join(plan)}")
    say(f"mode   {'DRY RUN' if DRY else 'APPLY'}")
    if not DRY and not ASSUME_YES:
        if input("\nproceed? [y/N] ").strip().lower() not in ("y", "yes"):
            return 1

    started = time.time()
    for name in plan:
        STAGES[name]()

    say(f"\n--- {len(set(TOUCHED))} path(s) touched in {time.time() - started:.1f}s")
    if not DRY and not args.build:
        say("build not run: re-run with --yes --build, or do it by hand from pegasus/ui/web")
    stage_git(args.commit)
    say(f"\nlog: {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())