import sys, os, threading, time, subprocess

from pegasus.ui.web.backend.app import create_app

app = create_app()

def run():
    print("Starting Pegasus Phantom Menace on port 5001...")
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False, threaded=True)

threading.Thread(target=run, daemon=True).start()
print("Server running at http://127.0.0.1:5001/")
time.sleep(3)
try:
    import urllib.request
    resp = urllib.request.urlopen("http://127.0.0.1:5000/", timeout=5)
    print("Health check:", resp.status)
except Exception as e:
    print("Check error:", e)
