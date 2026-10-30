#!/usr/bin/env python3
"""Pegasus Phantom Menace v2 — Web GUI launcher entry point.

Packaged by PyInstaller into a single executable. Supports the same flags as
``python -m pegasus.ui.web.server``.

    Pegasus-Web.exe                 # serve on 127.0.0.1:5000 and open browser
    Pegasus-Web.exe --port 8080     # custom port
    Pegasus-Web.exe --host 0.0.0.0  # expose on the LAN
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser


def _resource_root() -> str:
    """Return the directory holding bundled resources."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    # Make bundled packages importable when frozen.
    root = _resource_root()
    if root not in sys.path:
        sys.path.insert(0, root)

    import argparse

    parser = argparse.ArgumentParser(
        prog="Pegasus-Web",
        description="Pegasus Phantom Menace v2 — Android Security Audit Web GUI",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    parser.add_argument("--port", default=5000, type=int, help="bind port (default 5000)")
    parser.add_argument("--debug", action="store_true", help="enable Flask debug mode")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    args = parser.parse_args()

    from pegasus.ui.web.backend.app import create_app

    app = create_app()
    host_for_url = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    url = f"http://{host_for_url}:{args.port}/"

    banner = f"""
  PEGASUS: PHANTOM MENACE v2
  Android Device Management & Security Audit Platform

  Dashboard : {url}
  API       : {url}api/health
  Bind      : {args.host}:{args.port}

  Authorized security testing only. Press Ctrl+C to stop.
"""
    print(banner, flush=True)

    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        print("\nShutting down Pegasus.")
        time.sleep(0.3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
