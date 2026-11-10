import sys, os, threading, time, subprocess

from pegasus.ui.web.backend.app import create_app
from pegasus.core.config import port, host, base_url

app = create_app()

def run():
    print(f"Starting Pegasus Phantom Menace on port {port()}...")
    app.run(host=host(), port=port(), debug=False, use_reloader=False, threaded=True)

threading.Thread(target=run, daemon=True).start()
print(f"Server running at {base_url()}/")
time.sleep(3)
try:
    import urllib.request
    resp = urllib.request.urlopen(f"{base_url()}/api/health", timeout=5)
    print("Health check:", resp.status)
except Exception as e:
    print("Check error:", e)
