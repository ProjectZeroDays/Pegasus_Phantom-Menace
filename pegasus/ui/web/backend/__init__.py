"""Pegasus Web GUI backend package.

Bridges the Flask HTTP API to the Pegasus plugin system, workflow engine,
database, and local tooling (ADB, nmap, Frida, Metasploit).
"""

__all__ = ["create_app"]

from .app import create_app  # noqa: E402

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
