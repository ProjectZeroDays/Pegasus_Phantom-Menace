"""Fastboot, FRP, root-solution and Samsung/Odin routes.

Ported from the Q11 console. Every mutating route reports the exact command it
ran so the UI can show provenance. Views are fb_-prefixed.
"""
from __future__ import annotations

import os
import shlex

from flask import request, session

from pegasus.ui.web.backend.tools import run

AUTH_FLAG = "PEGASUS_REQUIRE_AUTH"
AUTH_TOKEN = "PEGASUS_API_TOKEN"

FRP_KEYS = [
    ("global", "device_provisioned", "1"),
    ("secure", "user_setup_complete", "1"),
    ("secure", "tv_user_setup_complete", "1"),
    ("global", "verifier_verify_adb_installs", "0"),
]

PLAY_KEYS = [
    ("global", "package_verifier_enable", "0"),
    ("secure", "package_verifier_user_consent", "-1"),
    ("global", "verifier_verify_adb_installs", "0"),
]


def _auth_on() -> bool:
    return os.environ.get(AUTH_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def _require_token(view):
    import functools

    @functools.wraps(view)
    def wrapper(*a, **k):
        if not _auth_on():
            return view(*a, **k)
        expected = os.environ.get(AUTH_TOKEN, "").strip()
        supplied = (
            request.headers.get("X-Pegasus-Token")
            or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            or request.args.get("token")
            or ""
        ).strip()
        if expected and supplied == expected:
            return view(*a, **k)
        if session.get("pegasus_user") or session.get("user"):
            return view(*a, **k)
        return {"ok": False, "error": "unauthorized"}, 401

    return wrapper


def _sh(serial: str, command: str, timeout: int = 60) -> dict:
    return run(["adb", "-s", serial, "shell", command], timeout=timeout)


def _fb(serial: str, args: list, timeout: int = 300) -> dict:
    argv = ["fastboot"]
    if serial:
        argv += ["-s", serial]
    return run(argv + [str(a) for a in args], timeout=timeout)


def _payload() -> dict:
    return request.get_json(silent=True) or {}


def _adb_state(serial: str) -> str:
    result = run(["adb", "devices"], timeout=20)
    for line in result.get("stdout", "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[0] == serial:
            return parts[1]
    return "absent"


def _fb_state(serial: str) -> str:
    result = run(["fastboot", "devices"], timeout=30)
    for line in result.get("stdout", "").splitlines():
        parts = line.split()
        if parts and (not serial or parts[0] == serial):
            return "fastboot"
    return "absent"


def _readback(serial: str, namespace: str, key: str) -> str:
    return _sh(serial, "settings get %s %s" % (namespace, key)).get("stdout", "").strip()


def _is_root(serial: str) -> bool:
    return _sh(serial, "su -c id -u").get("stdout", "").strip() == "0"


def _setting_write(serial: str, namespace: str, key: str, value: str) -> dict:
    """Root -> cmd -> content ladder, verified by readback."""
    uri = "content://settings/%s" % namespace
    missing = _readback(serial, namespace, key) in ("", "null")
    ladder = []
    if _is_root(serial):
        ladder.append(("su", "su -c \"settings put %s %s %s\"" % (namespace, key, value)))
    ladder.append(("cmd", "cmd settings put %s %s %s" % (namespace, key, value)))
    if missing:
        ladder.append(("content-insert",
                       "content insert --uri %s --bind name:s:%s --bind value:s:%s"
                       % (uri, key, value)))
    ladder.append(("settings", "settings put %s %s %s" % (namespace, key, value)))
    ladder.append(("content-update",
                   "content update --uri %s --bind value:s:%s --where \"name='%s'\""
                   % (uri, value, key)))
    tried = []
    for label, command in ladder:
        _sh(serial, command)
        got = _readback(serial, namespace, key)
        tried.append(label)
        if got == value:
            return {"key": key, "value": value, "via": label, "ok": True, "tried": tried}
    return {"key": key, "value": value, "via": None, "ok": False, "tried": tried}


def _clear_package(serial: str, pkg: str) -> bool:
    attempts = ["pm clear --user 0 %s" % pkg, "pm clear %s" % pkg]
    if _is_root(serial):
        attempts.insert(0, "su -c \"pm clear %s\"" % pkg)
    for command in attempts:
        if "Success" in _sh(serial, command).get("stdout", ""):
            return True
    return False


def register(app, ok, fail) -> None:  # noqa: ANN001
    # -- state -------------------------------------------------------------
    @app.get("/api/fastboot/<string:serial>/state")
    @_require_token
    def fb_state(serial):
        manufacturer = _sh(serial, "getprop ro.product.manufacturer").get("stdout", "").strip() \
            if _adb_state(serial) == "device" else ""
        return ok({
            "adb": _adb_state(serial),
            "fastboot": _fb_state(serial),
            "manufacturer": manufacturer,
            "samsung": "samsung" in manufacturer.lower(),
            "root": _is_root(serial) if _adb_state(serial) == "device" else False,
        })

    @app.get("/api/fastboot/engines")
    @_require_token
    def fb_engines():
        return ok({"engines": [
            {"key": "bootloader", "label": "Bootloader",
             "effects": ["unlock", "unlock-critical", "unlock-ability", "getvar"]},
            {"key": "flash", "label": "Flash",
             "effects": ["boot", "init_boot", "recovery", "vbmeta", "partition", "temp-boot"]},
            {"key": "verity", "label": "Verity", "effects": ["disable-verity"]},
            {"key": "slot", "label": "Slots", "effects": ["current-slot", "set-active"]},
            {"key": "carrier", "label": "Carrier / OEM",
             "effects": ["device-info", "unlock-data", "carrier-unlock"]},
            {"key": "erase", "label": "Erase", "effects": ["cache", "userdata"]},
            {"key": "frp", "label": "FRP", "effects": ["state", "chain", "play-protect"]},
            {"key": "root", "label": "Root",
             "effects": ["detect", "modules", "denylist", "install-module"]},
            {"key": "samsung", "label": "Samsung / Odin",
             "effects": ["detect", "download-mode", "heimdall-flash"]},
        ]})

    # -- FRP ---------------------------------------------------------------
    @app.get("/api/fastboot/<string:serial>/frp")
    @_require_token
    def fb_frp_state(serial):
        readings = {}
        for key, command in (
            ("frp", "dumpsys frp"),
            ("frp_partition", "getprop ro.frp.pst"),
            ("setup_complete", "settings get secure user_setup_complete"),
            ("provisioned", "settings get global device_provisioned"),
            ("accounts", "dumpsys account"),
        ):
            result = _sh(serial, command)
            readings[key] = result.get("stdout", "").strip()[:2500] if result.get("ok") else None
        readings["verdict"] = (
            "provisioned" if readings.get("setup_complete") == "1"
            and readings.get("provisioned") == "1" else "not provisioned"
        )
        return ok(readings)

    @app.post("/api/fastboot/<string:serial>/frp/chain")
    @_require_token
    def fb_frp_chain(serial):
        results = []
        for namespace, key, value in FRP_KEYS:
            results.append(_setting_write(serial, namespace, key, value))
        cleared = _clear_package(serial, "com.google.android.gms")
        _sh(serial, "am start -a com.google.android.setupwizard.SETUP_WIZARD_FINISHED")
        landed = sum(1 for r in results if r["ok"])
        verified = (
            _readback(serial, "secure", "user_setup_complete") == "1"
            and _readback(serial, "global", "device_provisioned") == "1"
        )
        return ok({"steps": results, "gms_cleared": cleared,
                   "landed": landed, "total": len(results), "verified": verified})

    @app.post("/api/fastboot/<string:serial>/play-protect")
    @_require_token
    def fb_play_protect(serial):
        results = [_setting_write(serial, ns, k, v) for ns, k, v in PLAY_KEYS]
        return ok({"steps": results, "landed": sum(1 for r in results if r["ok"]),
                   "total": len(results)})

    # -- bootloader --------------------------------------------------------
    @app.post("/api/fastboot/<string:serial>/unlock")
    @_require_token
    def fb_unlock(serial):
        ladder = [
            ["flashing", "unlock"],
            ["oem", "unlock"],
            ["flashing", "unlock_critical"],
            ["oem", "unlock-go"],
        ]
        results = []
        for args in ladder:
            result = _fb(serial, args, timeout=120)
            results.append({"command": " ".join(args),
                            "ok": result.get("ok", False),
                            "stdout": result.get("stdout", "").strip()[:400]})
            if result.get("ok") and "FAILED" not in result.get("stdout", "").upper():
                break
        return ok({"steps": results, "note": "device may wipe and reboot to confirm"})

    @app.get("/api/fastboot/<string:serial>/unlock-ability")
    @_require_token
    def fb_unlock_ability(serial):
        result = _fb(serial, ["flashing", "get_unlock_ability"], timeout=60)
        return ok({"raw": result.get("stdout", "").strip()[:600],
                   "ok": result.get("ok", False)})

    @app.get("/api/fastboot/<string:serial>/getvar")
    @_require_token
    def fb_getvar(serial):
        name = request.args.get("name", "all")
        result = _fb(serial, ["getvar", name], timeout=90)
        return ok({"name": name, "raw": (result.get("stdout", "") + result.get("stderr", "")).strip()[:8000]})

    # -- flash -------------------------------------------------------------
    @app.post("/api/fastboot/<string:serial>/flash")
    @_require_token
    def fb_flash(serial):
        body = _payload()
        partition = str(body.get("partition") or "").strip()
        path = str(body.get("path") or "").strip()
        if not partition or not path:
            return fail("partition and path required", 400)
        result = _fb(serial, ["flash", partition, path])
        return ok({"partition": partition, "path": path,
                   "ok": result.get("ok", False),
                   "stdout": (result.get("stdout", "") + result.get("stderr", "")).strip()[-800:]})

    @app.post("/api/fastboot/<string:serial>/temp-boot")
    @_require_token
    def fb_temp_boot(serial):
        path = str(_payload().get("path") or "").strip()
        if not path:
            return fail("path required", 400)
        result = _fb(serial, ["boot", path])
        return ok({"path": path, "ok": result.get("ok", False)})

    @app.post("/api/fastboot/<string:serial>/vbmeta")
    @_require_token
    def fb_vbmeta(serial):
        path = str(_payload().get("path") or "").strip()
        if not path:
            return fail("path required", 400)
        result = _fb(serial, ["--disable-verity", "--disable-verification",
                              "flash", "vbmeta", path])
        return ok({"path": path, "ok": result.get("ok", False)})

    @app.post("/api/fastboot/<string:serial>/disable-verity")
    @_require_token
    def fb_disable_verity(serial):
        result = _fb(serial, ["--disable-verity", "--disable-verification",
                              "flashing", "unlock"])
        return ok({"ok": result.get("ok", False),
                   "stdout": (result.get("stdout", "") + result.get("stderr", "")).strip()[-600:]})

    # -- slots -------------------------------------------------------------
    @app.get("/api/fastboot/<string:serial>/current-slot")
    @_require_token
    def fb_current_slot(serial):
        result = _fb(serial, ["getvar", "current-slot"], timeout=60)
        return ok({"raw": (result.get("stdout", "") + result.get("stderr", "")).strip()[:400]})

    @app.post("/api/fastboot/<string:serial>/set-active")
    @_require_token
    def fb_set_active(serial):
        slot = str(_payload().get("slot") or "a").strip()[:1]
        result = _fb(serial, ["--set-active=" + slot])
        return ok({"slot": slot, "ok": result.get("ok", False)})

    # -- carrier / OEM -----------------------------------------------------
    @app.get("/api/fastboot/<string:serial>/device-info")
    @_require_token
    def fb_device_info(serial):
        result = _fb(serial, ["oem", "device-info"], timeout=60)
        return ok({"raw": (result.get("stdout", "") + result.get("stderr", "")).strip()[:1200]})

    @app.get("/api/fastboot/<string:serial>/unlock-data")
    @_require_token
    def fb_unlock_data(serial):
        result = _fb(serial, ["oem", "get_unlock_data"], timeout=60)
        return ok({"raw": (result.get("stdout", "") + result.get("stderr", "")).strip()[:2000]})

    @app.post("/api/fastboot/<string:serial>/carrier-unlock")
    @_require_token
    def fb_carrier_unlock(serial):
        ladder = [["oem", "carrier-unlock"], ["oem", "sim-unlock"],
                  ["oem", "unlock-carrier"]]
        results = []
        for args in ladder:
            result = _fb(serial, args, timeout=120)
            results.append({"command": " ".join(args), "ok": result.get("ok", False),
                            "stdout": result.get("stdout", "").strip()[:300]})
        return ok({"steps": results})

    # -- erase -------------------------------------------------------------
    @app.post("/api/fastboot/<string:serial>/erase")
    @_require_token
    def fb_erase(serial):
        target = str(_payload().get("target") or "cache").strip()
        result = _fb(serial, ["erase", target])
        return ok({"target": target, "ok": result.get("ok", False)})

    @app.post("/api/fastboot/<string:serial>/userdata")
    @_require_token
    def fb_userdata(serial):
        result = _fb(serial, ["-w"], timeout=600)
        return ok({"ok": result.get("ok", False), "note": "wipes all user data"})

    @app.post("/api/fastboot/<string:serial>/reboot")
    @_require_token
    def fb_reboot(serial):
        target = str(_payload().get("target") or "").strip()
        result = _fb(serial, ["reboot"] + ([target] if target else []), timeout=120)
        return ok({"target": target or "system", "ok": result.get("ok", False)})

    # -- root solutions ----------------------------------------------------
    @app.get("/api/fastboot/<string:serial>/root/detect")
    @_require_token
    def fb_root_detect(serial):
        found = {}
        for label, command in (
            ("magisk_bin", "which magisk"),
            ("magisk_dir", "ls -d /data/adb/magisk"),
            ("ksud", "which ksud"),
            ("ksu_dir", "ls -d /data/adb/ksu"),
            ("apatch", "ls -d /data/adb/ap"),
        ):
            out = _sh(serial, command).get("stdout", "").strip()
            found[label] = out or None
        solution = ("magisk" if found["magisk_bin"] or found["magisk_dir"]
                    else "kernelsu" if found["ksud"] or found["ksu_dir"]
                    else "apatch" if found["apatch"] else "none")
        return ok({"solution": solution, "evidence": found, "uid0": _is_root(serial)})

    @app.get("/api/fastboot/<string:serial>/root/modules")
    @_require_token
    def fb_root_modules(serial):
        raw = _sh(serial, "ls /data/adb/modules").get("stdout", "").strip()
        return ok({"modules": [m for m in raw.splitlines() if m.strip()]})

    @app.get("/api/fastboot/<string:serial>/root/denylist")
    @_require_token
    def fb_root_denylist(serial):
        raw = _sh(serial, "magisk --denylist ls").get("stdout", "").strip()
        return ok({"packages": [p for p in raw.splitlines() if p.strip()]})

    @app.post("/api/fastboot/<string:serial>/root/install-module")
    @_require_token
    def fb_root_install_module(serial):
        path = str(_payload().get("path") or "").strip()
        if not path:
            return fail("path required", 400)
        quoted = shlex.quote(path)
        result = _sh(serial, "magisk --install-module %s" % quoted, timeout=180)
        return ok({"path": path, "ok": result.get("ok", False),
                   "stdout": (result.get("stdout", "") + result.get("stderr", "")).strip()[-600:]})

    # -- Samsung / Odin ----------------------------------------------------
    @app.get("/api/fastboot/<string:serial>/samsung/detect")
    @_require_token
    def fb_samsung_detect(serial):
        manufacturer = _sh(serial, "getprop ro.product.manufacturer").get("stdout", "").strip()
        model = _sh(serial, "getprop ro.product.model").get("stdout", "").strip()
        heimdall = run(["heimdall", "version"], timeout=30)
        odin = run(["odin", "--help"], timeout=30)
        return ok({
            "samsung": "samsung" in manufacturer.lower(),
            "manufacturer": manufacturer, "model": model,
            "heimdall": heimdall.get("ok", False),
            "odin_cli": odin.get("ok", False),
        })

    @app.post("/api/fastboot/<string:serial>/samsung/download-mode")
    @_require_token
    def fb_download_mode(serial):
        result = _sh(serial, "reboot download", timeout=30)
        return ok({"ok": result.get("ok", False),
                   "note": "device reboots to Odin/download mode"})

    @app.post("/api/fastboot/<string:serial>/samsung/heimdall")
    @_require_token
    def fb_heimdall(serial):
        body = _payload()
        partition = str(body.get("partition") or "").strip()
        path = str(body.get("path") or "").strip()
        if not partition or not path:
            return fail("partition and path required", 400)
        result = run(["heimdall", "flash", "--%s" % partition, path], timeout=900)
        return ok({"partition": partition, "path": path, "ok": result.get("ok", False),
                   "stdout": (result.get("stdout", "") + result.get("stderr", "")).strip()[-800:]})
