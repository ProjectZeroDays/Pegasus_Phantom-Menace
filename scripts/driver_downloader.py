#!/usr/bin/env python3
"""
scripts/driver_downloader.py

Download OEM Android USB drivers so the app can point Windows at them for
ADB device access. MobSF is an analysis platform (not a driver host), so
this fetches official OEM driver packages from each vendor's download page.

Drivers land in ~/.pegasus/drivers/<oem>/ and a manifest is written to
~/.pegasus/drivers/manifest.json.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DRIVERS_DIR = Path.home() / ".pegasus" / "drivers"
MANIFEST = DRIVERS_DIR / "manifest.json"

# OEM -> (name, download URL). URLs point to official vendor driver pages/packages.
OEM_DRIVERS = {
    "google": (
        "Google USB Driver",
        "https://dl.google.com/android/repository/google_usb_driver_r13.zip",
    ),
    "samsung": (
        "Samsung USB Driver",
        "https://developer.samsung.com/galaxy/others/android-usb-driver-for-windows",
    ),
    "xiaomi": (
        "Xiaomi USB Driver",
        "http://www.miui.com/sha.zip",
    ),
    "oneplus": (
        "OnePlus USB Driver",
        "https://www.oneplus.com/support/usbdriver",
    ),
    "google_pixel": (
        "Google Pixel USB Driver",
        "https://dl.google.com/android/repository/google_usb_driver_r13.zip",
    ),
    "motorola": (
        "Motorola USB Driver",
        "https://motorola-global-portal.custhelp.com/app/answers/detail/a_id/164482",
    ),
    "lg": (
        "LG USB Driver",
        "https://www.lg.com/us/support/mobile-phones/drivers",
    ),
    "huawei": (
        "Huawei USB Driver",
        "https://developer.huawei.com/consumer/en/",
    ),
    "oppo": (
        "OPPO USB Driver",
        "https://www.oppo.com/en/support/usb-driver",
    ),
    "vivo": (
        "vivo USB Driver",
        "https://www.vivo.com/en/support/usb-driver",
    ),
    "asus": (
        "ASUS USB Driver",
        "https://www.asus.com/support/",
    ),
    "sony": (
        "Sony USB Driver",
        "https://developer.sony.com/develop/open-devices/drivers/",
    ),
    "nokia": (
        "Nokia USB Driver",
        "https://www.nokia.com/phones/support/",
    ),
    "zte": (
        "ZTE USB Driver",
        "https://www.zte.com.cn/global/support/",
    ),
    "lenovo": (
        "Lenovo USB Driver",
        "https://support.lenovo.com/",
    ),
}


def download_driver(oem: str, info: tuple[str, str]) -> dict:
    name, url = info
    dest_dir = DRIVERS_DIR / oem
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = {"oem": oem, "name": name, "url": url, "status": "skipped", "detail": ""}
    # If the URL is a vendor page (not a direct binary), record it for manual download.
    if not any(ext in url for ext in (".zip", ".exe", ".msi", ".inf")):
        result["status"] = "page"
        result["detail"] = "vendor page — download manually"
        (dest_dir / "README.txt").write_text(
            f"Download {name} from: {url}\n", encoding="utf-8"
        )
        return result
    archive = dest_dir / (url.split("/")[-1] or "driver.bin")
    try:
        import requests
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(archive, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
        result["status"] = "downloaded"
        result["detail"] = str(archive)
    except Exception as exc:  # noqa: BLE001
        result["status"] = "error"
        result["detail"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> int:
    DRIVERS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for oem, info in OEM_DRIVERS.items():
        results.append(download_driver(oem, info))
    manifest = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "drivers": len(results),
        "downloaded": sum(1 for r in results if r["status"] == "downloaded"),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[driver_downloader] {manifest['downloaded']}/{manifest['drivers']} drivers "
          f"downloaded, {manifest['errors']} errors")
    for r in results:
        mark = "✓" if r["status"] == "downloaded" else ("○" if r["status"] == "page" else "✗")
        print(f"  {mark} {r['name']} ({r['oem']}): {r['detail'][:80]}")
    return 0 if manifest["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
