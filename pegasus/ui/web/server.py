"""Standalone launcher for the Pegasus web GUI.

Usage:
    python -m pegasus.ui.web.server --port 5000
    python -m pegasus.ui.web.server --host 0.0.0.0 --port 8080 --open
"""
from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

from .backend.app import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pegasus-web",
        description="Pegasus Phantom Menace v2 — Web GUI server",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    parser.add_argument("--port", default=5000, type=int, help="bind port (default 5000)")
    parser.add_argument("--debug", action="store_true", help="enable Flask debug mode")
    parser.add_argument("--open", action="store_true", help="open the dashboard in a browser")
    args = parser.parse_args(argv)

    app = create_app()
    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{args.port}/"

    if args.open:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    print(f"Pegasus web GUI : {url}")
    print(f"API health      : {url}api/health")
    print("Press Ctrl+C to stop.")
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
