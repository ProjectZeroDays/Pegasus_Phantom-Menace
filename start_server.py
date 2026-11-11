import sys, os, threading, time, subprocess

from pegasus.ui.web.backend.app import create_app
from pegasus.core.config import port, host, base_url

app = create_app()

def run():
    print(f"Starting Pegasus Phantom Menace on port {port()}...")
    app.run(host=host(), port=port(), debug=False, use_reloader=False, threaded=True)

# The server thread must NOT be a daemon: the desktop shell spawns this
# script and waits on the health endpoint, so if the interpreter exits the
# daemon thread dies with it and the console loses its backend seconds after
# launch.  A non-daemon thread keeps the process alive, and join() makes the
# intent explicit.
server = threading.Thread(target=run, daemon=False)
server.start()
print(f"Server running at {base_url()}/")
time.sleep(3)
try:
    import urllib.request
    resp = urllib.request.urlopen(f"{base_url()}/api/health", timeout=5)
    print("Health check:", resp.status)
except Exception as e:
    print("Check error:", e)

# Block until the server stops.
server.join()
