"""
ADB (Android Debug Bridge) Vector Scanner

Scans for ADB-exposed devices on TCP port 5555 and attempts
wireless ADB debugging exploitation.
"""
from __future__ import annotations

import socket
import subprocess
from typing import Any, Dict, Optional

from pegasus.modules.access_workflow.workflow_engine import VectorType


class ADBVector:
    """ADB access vector scanner and exploiter."""

    vector_type = VectorType.ADB
    default_port = 5555

    def scan(self, target: str, port: Optional[int] = None) -> Dict[str, Any]:
        port = port or self.default_port
        result = {
            "vector": "adb",
            "target": target,
            "port": port,
            "available": False,
            "vulnerable": False,
            "cve_ids": [],
            "banner": "",
            "confidence": 0.0,
            "notes": "",
        }

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            if sock.connect_ex((target, port)) == 0:
                result["available"] = True
                result["confidence"] = 0.9
                result["banner"] = "ADB service detected"
                result["notes"] = "ADB daemon listening on port 5555"

                # Try to connect via adb
                try:
                    conn_result = subprocess.run(
                        ["adb", "connect", f"{target}:{port}"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if "connected" in conn_result.stdout.lower():
                        result["vulnerable"] = True
                        result["cve_ids"] = ["CVE-2026-0073", "CVE-2023-26084"]
                        result["notes"] = "ADB connection established - device accessible"
                except Exception:
                    pass
            sock.close()
        except Exception as e:
            result["notes"] = f"Scan error: {e}"

        return result


# Module-level function for compatibility
def scan(target: str, port: Optional[int] = None) -> Dict[str, Any]:
    scanner = ADBVector()
    return scanner.scan(target, port)
