#!/usr/bin/env python3
"""Pegasus frontend restore + fix series + Fable scaffold and verification.

Phases, in this order:
  A  write src/lib (api, types, format, utils, useTelemetry) + device routes
  B  apply the fix series from the bug sweeps
  C  scaffold Fable, then verification steps 1-3 with a diagnostic ladder
  D  step 4 probe localhost:5173, step 5 print the LAN URL
  E  tsc, then commit

Flags: --no-fable  --no-commit  --fixes-only
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "pegasus" / "ui" / "web"
LIB = WEB / "src" / "lib"
BACKEND = WEB / "backend"
TEL = BACKEND / "telemetry.py"
ROUTES = BACKEND / "device_routes.py"
APP = BACKEND / "app.py"
API = LIB / "api.ts"
FSHARP = WEB / "fsharp"
FABLE_OUT = WEB / "src" / "fsharp" / "out"
FABLE_CFG = WEB / "fableconfig.json"

FILES: dict[Path, str] = {}

FILES[LIB / "utils.ts"] = r'''/** Class-name join with last-wins conflict resolution. */

type ClassValue = string | number | null | false | undefined | Record<string, boolean> | ClassValue[];

const FAMILIES: [RegExp, string][] = [
  [/^-?(m|p)[trblxy]?-(?:\d|\[)/, "spacing"],
  [/^(w|h|min-w|min-h|max-w|max-h)-/, "size"],
  [/^(text|bg|border|ring|fill|stroke)-/, "color"],
  [/^text-(?:xs|sm|base|lg|xl|\d)/, "fontsize"],
  [/^font-/, "weight"],
  [/^(flex|grid|block|inline|hidden|table)(?:-|$)/, "display"],
  [/^(items|justify|self|content)-/, "align"],
  [/^(rounded|shadow|opacity|z|gap)-?/, "box"],
];

function flatten(value: ClassValue, out: string[]): void {
  if (!value && value !== 0) return;
  if (typeof value === "string" || typeof value === "number") {
    for (const token of String(value).split(/\s+/)) if (token) out.push(token);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) flatten(item, out);
    return;
  }
  for (const [key, on] of Object.entries(value)) if (on) flatten(key, out);
}

function familyOf(token: string): string | null {
  const bare = token.replace(/^[a-z]+:/, "");
  for (const [pattern, name] of FAMILIES) if (pattern.test(bare)) return `${token.split(":")[0] ?? ""}|${name}`;
  return null;
}

/** Join conditional class values, dropping utilities a later class overrides. */
export function cn(...inputs: ClassValue[]): string {
  const tokens: string[] = [];
  flatten(inputs, tokens);
  const seen = new Map<string, number>();
  const kept: string[] = [];
  for (const token of tokens) {
    const family = familyOf(token);
    if (!family) {
      kept.push(token);
      continue;
    }
    const previous = seen.get(family);
    if (previous !== undefined) kept[previous] = "";
    seen.set(family, kept.length);
    kept.push(token);
  }
  return kept.filter(Boolean).join(" ");
}

export default cn;
'''

FILES[LIB / "format.ts"] = r'''/** Display formatters. All tolerate null, undefined and non-numeric input. */

const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"] as const;

function num(value: unknown): number | null {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatBytes(value: unknown, digits = 1): string {
  const bytes = num(value);
  if (bytes === null || bytes < 0) return "—";
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  let scale = 0;
  let size = bytes;
  while (size >= 1024 && scale < BYTE_UNITS.length - 1) {
    size /= 1024;
    scale += 1;
  }
  return `${size.toFixed(digits)} ${BYTE_UNITS[scale]}`;
}

export function formatNumber(value: unknown, digits = 0): string {
  const parsed = num(value);
  if (parsed === null) return "—";
  return parsed.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function toDate(value: unknown): Date | null {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === "number" || (typeof value === "string" && /^\d+$/.test(value))) {
    const numeric = Number(value);
    const ms = numeric > 1e11 ? numeric : numeric * 1000;
    const date = new Date(ms);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatTime(value: unknown): string {
  const date = toDate(value);
  return date ? date.toLocaleTimeString() : "—";
}

export function formatDateTime(value: unknown): string {
  const date = toDate(value);
  if (!date) return "—";
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

/** Duration from milliseconds. */
export function formatMs(value: unknown): string {
  const ms = num(value);
  if (ms === null || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return formatDuration(ms / 1000);
}

/** Duration from seconds. */
export function formatDuration(value: unknown): string {
  const seconds = num(value);
  if (seconds === null || seconds < 0) return "—";
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${rest}s`;
  return `${rest}s`;
}

/** Relative time from an epoch value in milliseconds. */
export function timeAgo(value: unknown): string {
  const date = toDate(value);
  if (!date) return "—";
  const delta = Math.round((Date.now() - date.getTime()) / 1000);
  if (delta < 0) return "just now";
  if (delta < 45) return "just now";
  if (delta < 3600) return `${Math.round(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.round(delta / 3600)}h ago`;
  if (delta < 2592000) return `${Math.round(delta / 86400)}d ago`;
  return date.toLocaleDateString();
}

export function titleCase(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export function initials(value: unknown): string {
  if (value === null || value === undefined) return "?";
  const words = String(value).trim().split(/\s+/).filter(Boolean);
  if (!words.length) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

const SEVERITY_TONES: Record<string, string> = {
  critical: "err",
  high: "warn",
  medium: "info",
  moderate: "info",
  low: "dim",
  info: "dim",
  none: "dim",
};

export function severityClass(value: unknown): string {
  const key = String(value ?? "").toLowerCase().trim();
  return SEVERITY_TONES[key] ?? "dim";
}
'''

FILES[LIB / "api.ts"] = r'''/** HTTP client for the Pegasus web GUI.
 *
 *  Two call styles coexist in the pages: bare paths ("/devices") and
 *  explicitly prefixed paths ("/api/catalog"). Both normalise onto a single
 *  base here so no page has to change.
 */
import { useCallback, useEffect, useRef, useState } from "react";

const RAW_BASE = String(import.meta.env?.VITE_API_BASE ?? "").replace(/\/+$/, "");
const BASE_IS_PREFIXED = /\/api$/i.test(RAW_BASE);
const API_ROOT = BASE_IS_PREFIXED ? RAW_BASE.replace(/\/api$/i, "") : RAW_BASE;

const DEFAULT_TIMEOUT = 30_000;

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/** Resolve a caller path onto the API root, exactly once. */
export function resolveUrl(path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  const alreadyPrefixed = clean === "/api" || clean.startsWith("/api/");
  if (alreadyPrefixed) return `${API_ROOT}${clean}`;
  return `${API_ROOT}/api${clean}`;
}

function csrf(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)(?:csrf_token|csrf)=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

interface RequestOptions {
  timeout?: number;
  signal?: AbortSignal;
  keepalive?: boolean;
}

async function request<T>(method: string, path: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeout ?? DEFAULT_TIMEOUT);
  const onAbort = () => controller.abort();
  options.signal?.addEventListener("abort", onAbort);

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = csrf();
  if (token) headers["X-CSRF-Token"] = token;

  try {
    const response = await fetch(resolveUrl(path), {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      keepalive: options.keepalive,
    });

    if (response.status === 204) return undefined as T;

    const text = await response.text();
    let parsed: unknown = null;
    if (text) {
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = text;
      }
    }

    const envelope = parsed as { ok?: boolean; data?: unknown; error?: unknown } | null;
    const failed = envelope && typeof envelope === "object" && envelope.ok === false;

    if (!response.ok || failed) {
      const message =
        (envelope && typeof envelope.error === "string" && envelope.error) ||
        (typeof parsed === "string" && parsed) ||
        `${response.status} ${response.statusText}`.trim();
      throw new ApiError(message, response.status, parsed);
    }

    if (envelope && typeof envelope === "object" && "ok" in envelope) {
      return (envelope.data ?? null) as T;
    }
    return parsed as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as Error)?.name === "AbortError") {
      throw new ApiError("request timed out", 0, null);
    }
    throw new ApiError((error as Error)?.message || "network error", 0, null);
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", onAbort);
  }
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>("GET", path, undefined, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>("POST", path, body, options),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>("PUT", path, body, options),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>("PATCH", path, body, options),
  del: <T>(path: string, options?: RequestOptions) => request<T>("DELETE", path, undefined, options),
};

export interface UseApiOptions {
  interval?: number;
  enabled?: boolean;
  deps?: unknown[];
}

export interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => void;
}

/** Poll a path. A null path suspends the request without unmounting. */
export function useApi<T>(path: string | null, options: UseApiOptions = {}): UseApiResult<T> {
  const { interval, enabled = true, deps = [] } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const serial = useRef(0);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);

  const fetchNow = useCallback(async () => {
    if (!path || !enabled) return;
    const ticket = ++serial.current;
    setLoading(true);
    try {
      const result = await api.get<T>(path);
      if (!active.current || ticket !== serial.current) return;
      setData(result);
      setError(null);
    } catch (caught) {
      if (!active.current || ticket !== serial.current) return;
      setError(caught as Error);
    } finally {
      if (active.current && ticket === serial.current) setLoading(false);
    }
  }, [path, enabled]);

  const refresh = useCallback(() => {
    void fetchNow();
  }, [fetchNow]);

  useEffect(() => {
    void fetchNow();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchNow, ...deps]);

  useEffect(() => {
    if (!interval || !path || !enabled) return;
    const timer = setInterval(() => void fetchNow(), interval);
    return () => clearInterval(timer);
  }, [interval, path, enabled, fetchNow]);

  return { data, loading, error, refresh };
}

export default api;
'''

FILES[LIB / "useTelemetry.ts"] = r'''/** Device telemetry hook: reads the latest sample, triggers collection. */
import { useCallback, useEffect, useRef } from "react";
import { api, useApi } from "@/lib/api";
import type { TelemetrySample } from "@/lib/types";
import { useApp } from "@/state/AppContext";

const BURST_DELAYS = [600, 1200, 2400];

export interface UseTelemetryResult<T> {
  data: TelemetrySample<T> | null;
  loading: boolean;
  error: Error | null;
  refresh: () => void;
  collect: () => Promise<void>;
  serial: string | null;
  burst: () => void;
}

export function useTelemetry<T>(kind: string, ttl = 30_000): UseTelemetryResult<T> {
  const { activeSerial } = useApp() as { activeSerial: string | null };
  const serial = activeSerial ?? null;
  const timers = useRef<number[]>([]);

  const path = serial ? `/devices/${encodeURIComponent(serial)}/telemetry/${kind}` : null;
  const { data, loading, error, refresh } = useApi<TelemetrySample<T>>(path, {
    interval: ttl,
    enabled: Boolean(serial),
    deps: [serial, kind],
  });

  const clearTimers = useCallback(() => {
    for (const timer of timers.current) window.clearTimeout(timer);
    timers.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers, serial, kind]);

  const burst = useCallback(() => {
    clearTimers();
    for (const delay of BURST_DELAYS) {
      timers.current.push(window.setTimeout(() => refresh(), delay));
    }
  }, [clearTimers, refresh]);

  const collect = useCallback(async () => {
    if (!serial) return;
    await api.post(`/devices/${encodeURIComponent(serial)}/telemetry/${kind}/collect`);
    refresh();
  }, [serial, kind, refresh]);

  return { data, loading, error, refresh, collect, serial, burst };
}

export default useTelemetry;
'''

FILES[FSHARP / "Pegasus.Core.fsproj"] = '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <LangVersion>latest</LangVersion>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="Format.fs" />
  </ItemGroup>
  <ItemGroup>
    <PackageReference Include="Fable.Core" Version="4.*" />
  </ItemGroup>
</Project>
'''

FILES[FSHARP / "Format.fs"] = '''module Pegasus.Fsharp.Format

/// Compact duration from seconds. Mirrors formatDuration in lib/format.ts.
let duration (seconds: int) : string =
    if seconds < 60 then sprintf "%ds" seconds
    elif seconds < 3600 then sprintf "%dm %ds" (seconds / 60) (seconds % 60)
    else sprintf "%dh %dm" (seconds / 3600) (seconds % 3600 / 60)
'''

FILES[FABLE_CFG] = json.dumps(
    {"outDir": "src/fsharp/out", "extension": ".ts", "sourceMaps": True, "verbose": False},
    indent=2,
) + "\n"

FILES[LIB / "fsharp-check.ts"] = '''/** Compile-time proof that Fable output typechecks. Imported by nothing. */
export { duration } from "@/fsharp/out/Format";
'''


def sh(cmd, cwd: Path | None = None) -> int:
    printable = " ".join(cmd) if isinstance(cmd, list) else cmd
    print(f"  $ {printable}")
    return subprocess.call(cmd, cwd=str(cwd or ROOT), shell=isinstance(cmd, str))


def phase_a() -> None:
    print("A  lib + routes")
    for path, content in FILES.items():
        if path.suffix == ".ts" and "/fsharp/" in str(path).replace("\\", "/") and "out" not in str(path):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  wrote {path.relative_to(ROOT)}")


EDITS: list[tuple[Path, str, str, str]] = []


def edit(path: Path, name: str, old: str, new: str) -> None:
    EDITS.append((path, name, old, new))


edit(TEL, "import contextlib", r'''import json
import re''', r'''import contextlib
import json
import re''')

edit(TEL, "import Iterator", r'''from typing import Any, Dict, Iterable, List, Optional''',
     r'''from typing import Any, Dict, Iterable, Iterator, List, Optional''')

edit(TEL, "conn contextmanager", r'''def init_store() -> None:''', r'''@contextlib.contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    """Connection that commits on success and always closes.

    `with _connect() as conn` only commits; the connection is not closed, so
    every call leaked a descriptor.
    """
    conn = _connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_store() -> None:''')

edit(TEL, "use _conn", "with _LOCK, _connect() as conn", "with _LOCK, _conn() as conn")

edit(ROUTES, "drop duplicate init_store", r'''    telemetry.init_store()

''', "")

edit(APP, "import secrets", r'''import pathlib
import uuid''', r'''import pathlib
import secrets
import uuid''')

edit(APP, "persist secret once", r'''    app.secret_key = pathlib.Path.home().joinpath(".pegasus", ".secret").read_text() \
        if pathlib.Path.home().joinpath(".pegasus", ".secret").exists() else uuid.uuid4().hex''',
     r'''    secret_file = pathlib.Path.home().joinpath(".pegasus", ".secret")
    if not secret_file.exists():
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text(secrets.token_hex(32), encoding="utf-8")
        try:
            secret_file.chmod(0o600)
        except OSError:
            pass
    app.secret_key = secret_file.read_text(encoding="utf-8").strip()''')

edit(API, "redirect on setup gate", r'''      throw new ApiError(message, response.status, parsed);''',
     r'''      if (response.status === 428 && !window.location.pathname.startsWith("/setup")) {
        window.location.assign("/setup");
      }
      throw new ApiError(message, response.status, parsed);''')

edit(ROUTES, "exec-out media", r'''    @app.get("/api/devices/<serial>/media/<int:media_id>/raw")
    def media_raw(serial, media_id):
        for uri in MEDIA_URIS.values():
            result = run(
                ["adb", "-s", serial, "shell", "content", "read", "--uri", f"{uri}/{media_id}"],
                timeout=60,
            )
            if result.get("ok") and result.get("stdout"):
                data = result["stdout"].encode("latin-1", errors="replace")
                return Response(data, mimetype=mimetypes.guess_type(f"x{media_id}")[0] or "image/jpeg")
        return fail("media unavailable", 404)''',
     r'''    @app.get("/api/devices/<serial>/media/<int:media_id>/raw")
    def media_raw(serial, media_id):
        import subprocess
        # exec-out keeps stdout byte-exact; `shell` mangles anything above 0x7F.
        for uri in MEDIA_URIS.values():
            proc = subprocess.run(
                ["adb", "-s", serial, "exec-out", "content", "read", "--uri", f"{uri}/{media_id}"],
                capture_output=True,
                timeout=120,
            )
            if proc.returncode == 0 and proc.stdout:
                magic = proc.stdout[:8]
                if magic[:3] == b"\xff\xd8\xff":
                    mime = "image/jpeg"
                elif magic[:4] == b"\x89PNG":
                    mime = "image/png"
                elif magic[4:8] == b"ftyp":
                    mime = "video/mp4"
                else:
                    mime = "application/octet-stream"
                return Response(proc.stdout, mimetype=mime)
        return fail("media unavailable", 404)''')

edit(TEL, "collect emails", r'''        if phone not in entry["phones"]:
            entry["phones"].append(phone)
    return list(contacts.values())''',
     r'''        if phone not in entry["phones"]:
            entry["phones"].append(phone)
    for row in content_query(
        serial,
        "content://com.android.contacts/data/emails",
        "display_name:data1",
    ):
        name = row.get("display_name") or "Unknown"
        email = row.get("data1") or ""
        if not email or name not in contacts:
            continue
        if email not in contacts[name]["emails"]:
            contacts[name]["emails"].append(email)
    return list(contacts.values())''')

edit(TEL, "call projection", '"number:date:duration:type:name:cache"',
     '"number:date:duration:type:name:cached_name"')

edit(TEL, "return media rows", r'''            save_samples(serial, "videos", result.get("videos", []))
        return []''',
     r'''            save_samples(serial, "videos", result.get("videos", []))
        return result.get("photos", []) + result.get("videos", [])''')

edit(TEL, "batch dumpsys", r'''    # Enrich with version/size for the first 40 apps (bounded work).
    for app in apps[:40]:
        dump = run(
            ["adb", "-s", serial, "shell", "dumpsys", "package", app["packageName"]],
            timeout=12,
        )
        match = re.search(r"versionName=(\S+)", dump["stdout"])
        if match:
            app["version"] = match.group(1)
    return apps''',
     r'''    # One dumpsys for the whole device instead of 40 sequential round-trips.
    dump = run(["adb", "-s", serial, "shell", "dumpsys", "package", "packages"], timeout=90)
    versions: Dict[str, str] = {}
    current = None
    for line in dump["stdout"].splitlines():
        header = re.match(r"\s*Package \[([\w.]+)\]", line)
        if header:
            current = header.group(1)
            continue
        if current:
            match = re.search(r"versionName=(\S+)", line)
            if match:
                versions[current] = match.group(1)
                current = None
    for app in apps:
        app["version"] = versions.get(app["packageName"], "")
    return apps''')

edit(TEL, "parallel summary", r'''    contacts = latest_or_collect(serial, "contacts")
    sms = latest_or_collect(serial, "sms")
    calls = latest_or_collect(serial, "calls")
    browser = latest_or_collect(serial, "browser")
    apps = latest_or_collect(serial, "apps")
    locations = latest_or_collect(serial, "locations")''',
     r'''    kinds = ("contacts", "sms", "calls", "browser", "apps", "locations")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(kinds)) as pool:
        gathered = dict(zip(kinds, pool.map(lambda k: latest_or_collect(serial, k), kinds)))
    contacts = gathered["contacts"]
    sms = gathered["sms"]
    calls = gathered["calls"]
    browser = gathered["browser"]
    apps = gathered["apps"]
    locations = gathered["locations"]''')

edit(TEL, "import futures", r'''import contextlib
import json''', r'''import concurrent.futures
import contextlib
import json''')


def phase_b() -> int:
    print("B  fix series")
    touched: set[Path] = set()
    for path, name, old, new in EDITS:
        text = path.read_text(encoding="utf-8")
        if old not in text:
            print(f"  FAIL {path.relative_to(ROOT)} :: {name}")
            print(f"       anchor missing: {old[:120]!r}")
            return 2
        path.write_text(text.replace(old, new), encoding="utf-8")
        touched.add(path)
        print(f"  ok   {path.relative_to(ROOT)} :: {name}")
    for path in sorted(touched):
        if path.suffix == ".py":
            if subprocess.call([sys.executable, "-m", "py_compile", str(path)]) != 0:
                print(f"  compile failed {path}")
                return 3
    print("  py_compile clean")
    return 0


def node_major() -> int | None:
    try:
        out = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=20)
        return int(out.stdout.strip().lstrip("v").split(".")[0])
    except Exception:
        return None


def diagnose_fable() -> list[str]:
    """Ordered causes from the verification note. Returns applicable ones."""
    causes = []
    try:
        cfg = json.loads(FABLE_CFG.read_text(encoding="utf-8"))
        if not cfg.get("outDir"):
            causes.append("1. outDir missing from fableconfig.json")
    except Exception:
        causes.append("1. fableconfig.json unreadable or missing outDir")
    try:
        proj = (FSHARP / "Pegasus.Core.fsproj").read_text(encoding="utf-8")
        if "Format.fs" not in proj:
            causes.append("2. Format.fs absent from <Compile Include>")
    except Exception:
        causes.append("2. fsproj missing")
    major = node_major()
    if major is None or major < 20:
        causes.append(f"3. Node below 20 (found {major or 'none'})")
    return causes


def phase_c() -> int:
    print("C  fable scaffold + verification 1-3")
    if subprocess.call(["where", "dotnet"], capture_output=True).returncode != 0:
        print("  dotnet not on PATH — skipping C and D")
        return 0
    ver = subprocess.run(["dotnet", "--version"], capture_output=True, text=True)
    print(f"  step 1  dotnet {ver.stdout.strip()}")

    if subprocess.call(["where", "fable"], capture_output=True).returncode != 0:
        print("  fable not installed — run: dotnet tool install --global fable")
        print("  then re-run with --no-commit to finish phase C")
        return 0

    got = subprocess.run(["fable", "--version"], capture_output=True, text=True)
    if got.returncode != 0:
        print(f"  step 1 FAILED: fable --version -> {got.returncode}")
        return 0
    print(f"  step 1  fable {got.stdout.strip() or got.stderr.strip()}")

    for path in (FSHARP / "Pegasus.Core.fsproj", FSHARP / "Format.fs", FABLE_CFG):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(FILES[path], encoding="utf-8")
        print(f"  wrote {path.relative_to(ROOT)}")
    (LIB / "fsharp-check.ts").write_text(FILES[LIB / "fsharp-check.ts"], encoding="utf-8")

    FABLE_OUT.mkdir(parents=True, exist_ok=True)
    print("  step 2  fable fsharp --lang ts")
    build = subprocess.run(["fable", "fsharp", "--lang", "ts"], cwd=str(WEB), capture_output=True, text=True)
    target = FABLE_OUT / "Format.ts"
    if build.returncode != 0 or not target.exists():
        print(f"  step 2 FAILED (rc={build.returncode})")
        print((build.stdout or "")[-1500:])
        print((build.stderr or "")[-1500:])
        print("  diagnostic ladder:")
        for cause in diagnose_fable() or ["no listed cause matched — inspect fableconfig.json by hand"]:
            print(f"    {cause}")
        return 0
    print(f"  step 2  wrote {target.relative_to(ROOT)} ({target.stat().st_size} bytes)")
    print("  step 3  see phase E")
    return 0


def lan_ip() -> str | None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return None


def phase_d() -> None:
    print("D  reachability")
    try:
        with urllib.request.urlopen("http://127.0.0.1:5173", timeout=4) as response:
            print(f"  step 4  localhost:5173 -> {response.status}")
    except (urllib.error.URLError, OSError) as exc:
        print(f"  step 4  localhost:5173 not up ({exc.__class__.__name__})")
        print("          start it: npm run dev -- --host 0.0.0.0")
    ip = lan_ip()
    if ip:
        print(f"  step 5  open in Safari: http://{ip}:5173")
        print(f'          netsh advfirewall firewall add rule name="Pegasus Vite" dir=in action=allow protocol=TCP localport=5173')
        print("          iOS 16+ will prompt for Local Network — deny it and the page hangs silently")


def main() -> int:
    if not (WEB / "src" / "pages").is_dir():
        print("run from the repo root")
        return 1

    phase_a()
    if "--fixes-only" not in sys.argv:
        code = phase_b()
        if code:
            return code
    if "--no-fable" not in sys.argv:
        phase_c()

    print("E  typecheck")
    if subprocess.call("npx tsc --noEmit", cwd=str(WEB), shell=True) != 0:
        print("  tsc failed — not committing")
        return 4
    print("  tsc clean")

    phase_d()

    if "--no-commit" in sys.argv:
        print("\n--no-commit set")
        return 0

    subprocess.call("git add -A", cwd=str(ROOT), shell=True)
    subprocess.call(
        'git commit -m "web: restore src/lib, add device routes, apply fix series, scaffold fable" '
        '-m "Sweeps 5.1 5.3 7.1 7.2 8.1 8.2 8.3 10.1 12.3."',
        cwd=str(ROOT), shell=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())