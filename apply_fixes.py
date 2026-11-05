#!/usr/bin/env python3
"""Fix series: sweeps 5.1, 5.3, 7.1, 7.2, 8.1, 8.2, 8.3, 10.1, 12.3.

Every edit is anchored with an assert. Run from the repo root, after
apply_lib.py. Use --no-commit to inspect first.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "pegasus" / "ui" / "web"
TEL = WEB / "backend" / "telemetry.py"
ROUTES = WEB / "backend" / "device_routes.py"
APP = WEB / "backend" / "app.py"
API = WEB / "src" / "lib" / "api.ts"

EDITS: list[tuple[Path, str, str, str]] = []


def edit(path: Path, name: str, old: str, new: str) -> None:
    EDITS.append((path, name, old, new))


# ---------------------------------------------------------------- 5.1 leak
edit(TEL, "conn contextmanager", '''def init_store() -> None:''', '''@contextlib.contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    """Connection that commits on success and always closes.

    `with _connect() as conn` only commits — the connection object is not a
    context manager for closing, so every call leaked a descriptor.
    """
    conn = _connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_store() -> None:''')

edit(TEL, "import contextlib", '''import json
import re''', '''import contextlib
import json
import re''')

edit(TEL, "import Iterator", '''from typing import Any, Dict, Iterable, List, Optional''',
     '''from typing import Any, Dict, Iterable, Iterator, List, Optional''')

edit(TEL, "use _conn", "with _LOCK, _connect() as conn", "with _LOCK, _conn() as conn")

# ------------------------------------------------- 5.3 import-time side effect
edit(ROUTES, "drop duplicate init_store", '''    telemetry.init_store()

''', "")

# ------------------------------------------------- 7.1 stable secret key
edit(APP, "import secrets", "import pathlib\nimport uuid",
     "import pathlib\nimport secrets\nimport uuid")

edit(APP, "persist secret once", '''    app.secret_key = pathlib.Path.home().joinpath(".pegasus", ".secret").read_text() \\
        if pathlib.Path.home().joinpath(".pegasus", ".secret").exists() else uuid.uuid4().hex''',
     '''    secret_file = pathlib.Path.home().joinpath(".pegasus", ".secret")
    if not secret_file.exists():
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text(secrets.token_hex(32), encoding="utf-8")
        try:
            secret_file.chmod(0o600)
        except OSError:
            pass
    app.secret_key = secret_file.read_text(encoding="utf-8").strip()''')

# ------------------------------------------------- 7.2 honour the 428 gate
edit(API, "redirect on setup gate", '''      throw new ApiError(message, response.status, parsed);''',
     '''      if (response.status === 428 && !window.location.pathname.startsWith("/setup")) {
        window.location.assign("/setup");
      }
      throw new ApiError(message, response.status, parsed);''')

# ------------------------------------------------- 12.3 binary media
edit(ROUTES, "exec-out media", '''    @app.get("/api/devices/<serial>/media/<int:media_id>/raw")
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
     '''    @app.get("/api/devices/<serial>/media/<int:media_id>/raw")
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
                magic = proc.stdout[:4]
                if magic[:3] == b"\\xff\\xd8\\xff":
                    mime = "image/jpeg"
                elif magic[:4] == b"\\x89PNG":
                    mime = "image/png"
                elif proc.stdout[4:8] == b"ftyp":
                    mime = "video/mp4"
                else:
                    mime = "application/octet-stream"
                return Response(proc.stdout, mimetype=mime)
        return fail("media unavailable", 404)''')

# ------------------------------------------------- 8.1 contact emails
edit(TEL, "collect emails", '''        if phone not in entry["phones"]:
            entry["phones"].append(phone)
    return list(contacts.values())''',
     '''        if phone not in entry["phones"]:
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

# ------------------------------------------------- 8.2 call name column
edit(TEL, "call projection", '"number:date:duration:type:name:cache"',
     '"number:date:duration:type:name:cached_name"')

# ------------------------------------------------- 8.3 media collect return
edit(TEL, "return media rows", '''            save_samples(serial, "videos", result.get("videos", []))
        return []''',
     '''            save_samples(serial, "videos", result.get("videos", []))
        return result.get("photos", []) + result.get("videos", [])''')

# ------------------------------------------------- 10.1 batch app versions
edit(TEL, "batch dumpsys", '''    # Enrich with version/size for the first 40 apps (bounded work).
    for app in apps[:40]:
        dump = run(
            ["adb", "-s", serial, "shell", "dumpsys", "package", app["packageName"]],
            timeout=12,
        )
        match = re.search(r"versionName=(\\S+)", dump["stdout"])
        if match:
            app["version"] = match.group(1)
    return apps''',
     '''    # One dumpsys for the whole device instead of 40 sequential round-trips.
    dump = run(["adb", "-s", serial, "shell", "dumpsys", "package", "packages"], timeout=90)
    versions: Dict[str, str] = {}
    current = None
    for line in dump["stdout"].splitlines():
        header = re.match(r"\\s*Package \\[([\\w.]+)\\]", line)
        if header:
            current = header.group(1)
            continue
        if current:
            match = re.search(r"versionName=(\\S+)", line)
            if match:
                versions[current] = match.group(1)
                current = None
    for app in apps:
        app["version"] = versions.get(app["packageName"], "")
    return apps''')

# ------------------------------------------------- 8.5 parallel summary
edit(TEL, "parallel summary", '''    contacts = latest_or_collect(serial, "contacts")
    sms = latest_or_collect(serial, "sms")
    calls = latest_or_collect(serial, "calls")
    browser = latest_or_collect(serial, "browser")
    apps = latest_or_collect(serial, "apps")
    locations = latest_or_collect(serial, "locations")''',
     '''    kinds = ("contacts", "sms", "calls", "browser", "apps", "locations")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(kinds)) as pool:
        gathered = dict(zip(kinds, pool.map(lambda k: latest_or_collect(serial, k), kinds)))
    contacts = gathered["contacts"]
    sms = gathered["sms"]
    calls = gathered["calls"]
    browser = gathered["browser"]
    apps = gathered["apps"]
    locations = gathered["locations"]''')

edit(TEL, "import futures", "import contextlib\nimport json", "import concurrent.futures\nimport contextlib\nimport json")


def main() -> int:
    if not TEL.exists():
        print("run apply_lib.py first"); return 1

    touched: set[Path] = set()
    for path, name, old, new in EDITS:
        text = path.read_text(encoding="utf-8")
        if old not in text:
            print(f"FAIL  {path.relative_to(ROOT)} :: {name}")
            print(f"      anchor not found:\n{old[:180]}\n")
            return 2
        count = text.count(old)
        path.write_text(text.replace(old, new), encoding="utf-8")
        touched.add(path)
        print(f"  ok  {path.relative_to(ROOT)} :: {name}  ({count}x)")

    print("\nsyntax check")
    for path in sorted(touched):
        if path.suffix == ".py":
            r = subprocess.call([sys.executable, "-m", "py_compile", str(path)])
            if r != 0:
                print(f"  compile failed: {path}"); return 3
            print(f"  ok  {path.relative_to(ROOT)}")

    print("\ntypecheck")
    if subprocess.call("npx tsc --noEmit", cwd=str(WEB), shell=True) != 0:
        print("tsc failed"); return 4

    if "--no-commit" in sys.argv:
        print("clean, --no-commit"); return 0

    subprocess.call("git add -A", cwd=str(ROOT), shell=True)
    subprocess.call(
        'git commit -m "backend: fix telemetry leaks, media transport, secret key, scan cost" '
        '-m "Closes sweeps 5.1 5.3 7.1 7.2 8.1 8.2 8.3 10.1 12.3."',
        cwd=str(ROOT), shell=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())