#!/usr/bin/env python3
"""Repair pass: dedupe re-applied edits, then finish the remaining fix series."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import apply_lib as L

ROOT: Path = L.ROOT
TEL = L.TEL
APP = L.APP
ROUTES = L.ROUTES
API = L.API

CONN_MARKER = "@contextlib.contextmanager\ndef _conn()"
CONN_END = "        conn.close()\n"


def dedupe_imports(text: str) -> str:
    out: list[str] = []
    for line in text.split("\n"):
        if out and line == out[-1] and line.startswith("import "):
            continue
        out.append(line)
    return "\n".join(out)


def dedupe_conn(text: str) -> str:
    first = text.find(CONN_MARKER)
    if first == -1:
        return text
    end = text.find(CONN_END, first)
    if end == -1:
        return text
    end += len(CONN_END)
    search = end
    while True:
        start = text.find(CONN_MARKER, search)
        if start == -1:
            break
        stop = text.find(CONN_END, start)
        if stop == -1:
            break
        stop += len(CONN_END)
        while text[stop:stop + 1] == "\n":
            stop += 1
        text = text[:start] + text[stop:]
        search = start
    return text


EDITS: list[tuple[Path, str, str, str, str]] = []


def edit(path: Path, name: str, marker: str, old: str, new: str) -> None:
    EDITS.append((path, name, marker, old, new))


edit(APP, "import secrets", "import secrets", "", "")

edit(APP, "persist secret once", "secret_file =", r'''    app.secret_key = pathlib.Path.home().joinpath(".pegasus", ".secret").read_text() \
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

edit(API, "redirect on setup gate", "=== 428", r'''      throw new ApiError(message, response.status, parsed);''',
     r'''      if (response.status === 428 && !window.location.pathname.startsWith("/setup")) {
        window.location.assign("/setup");
      }
      throw new ApiError(message, response.status, parsed);''')

edit(ROUTES, "exec-out media", "exec-out", r'''    @app.get("/api/devices/<serial>/media/<int:media_id>/raw")
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

edit(TEL, "collect emails", "data/emails", r'''        if phone not in entry["phones"]:
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

edit(TEL, "call projection", "cached_name", '"number:date:duration:type:name:cache"',
     '"number:date:duration:type:name:cached_name"')

edit(TEL, "return media rows", 'result.get("photos", []) + result.get("videos"', r'''            save_samples(serial, "videos", result.get("videos", []))
        return []''',
     r'''            save_samples(serial, "videos", result.get("videos", []))
        return result.get("photos", []) + result.get("videos", [])''')

edit(TEL, "batch dumpsys", r"Package \[([\w.]+)\]", r'''    # Enrich with version/size for the first 40 apps (bounded work).
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

edit(TEL, "parallel summary", "ThreadPoolExecutor", r'''    contacts = latest_or_collect(serial, "contacts")
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

edit(TEL, "import futures", "import concurrent.futures", r'''import contextlib
import json''', r'''import concurrent.futures
import contextlib
import json''')


def clean() -> int:
    print("A  dedupe")
    text = TEL.read_text(encoding="utf-8")
    before = (text.count("import contextlib"), text.count(CONN_MARKER))
    text = dedupe_conn(dedupe_imports(text))
    TEL.write_text(text, encoding="utf-8")
    after = (text.count("import contextlib"), text.count(CONN_MARKER))
    print(f"  contextlib {before[0]} -> {after[0]}   _conn def {before[1]} -> {after[1]}")
    if after != (1, 1):
        print("  unexpected counts after dedupe")
        return 2
    return 0


def apply_edits() -> int:
    print("B  remaining edits")
    touched: set[Path] = set()
    for path, name, marker, old, new in EDITS:
        text = path.read_text(encoding="utf-8")

        if name == "import secrets":
            if "import secrets" in text:
                print(f"  skip  {path.name} :: {name}")
                continue
            anchor = "\nfrom flask import Flask, jsonify"
            if anchor not in text:
                print(f"  FAIL  {path.name} :: {name} (no flask import line)")
                return 2
            text = text.replace(anchor, "\nimport secrets" + anchor, 1)
            path.write_text(text, encoding="utf-8")
            touched.add(path)
            print(f"  ok    {path.name} :: {name}")
            continue

        if marker and marker in text:
            print(f"  skip  {path.name} :: {name} (already applied)")
            continue
        if old not in text:
            print(f"  FAIL  {path.name} :: {name}")
            print(f"        anchor missing: {old[:110]!r}")
            return 2
        path.write_text(text.replace(old, new), encoding="utf-8")
        touched.add(path)
        print(f"  ok    {path.name} :: {name}")

    for path in sorted(touched):
        if path.suffix == ".py":
            if subprocess.call([sys.executable, "-m", "py_compile", str(path)]) != 0:
                print(f"  compile failed {path}")
                return 3
    print("  py_compile clean")
    return 0


def main() -> int:
    if not (L.WEB / "src" / "pages").is_dir():
        print("run from the repo root"); return 1

    code = clean()
    if code:
        return code
    code = apply_edits()
    if code:
        return code

    print("\nimport smoke test")
    smoke = subprocess.run(
        [sys.executable, "-c", "import ast,pathlib;ast.parse(pathlib.Path(r'%s').read_text(encoding='utf-8'))" % TEL],
        capture_output=True, text=True,
    )
    print("  ast ok" if smoke.returncode == 0 else f"  ast failed: {smoke.stderr[-400:]}")

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