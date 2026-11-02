#!/usr/bin/env python3
"""Pegasus Phantom Menace v2.1 — Web GUI launcher."""
from __future__ import annotations
import os, sys, threading, time, webbrowser, argparse

def _resource_root():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def main() -> int:
    root = _resource_root()
    if root not in sys.path: sys.path.insert(0, root)
    parser = argparse.ArgumentParser(prog="Pegasus-Web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5000, type=int)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    from pegasus.ui.web.backend.app import create_app
    app = create_app()
    url = f"http://{('127.0.0.1' if args.host in ('0.0.0.0','::') else args.host)}:{args.port}/"
    print(f"\n  PEGASUS v2.1 — Web GUI\n  Dashboard : {url}\n  API       : {url}api/health\n")
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down Pegasus.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
