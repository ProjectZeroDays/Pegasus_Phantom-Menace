"""cloudflared preferred, ngrok fallback."""
import os
import re
import shutil
import subprocess
import threading

URL_RE = re.compile(r"https://[a-z0-9-]+\.(?:trycloudflare\.com|ngrok(?:-free)?\.(?:io|app))")


class Tunnel:
    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.url: str | None = None

    def start(self, port: int) -> str | None:
        if shutil.which("cloudflared"):
            cmd = ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}",
                   "--no-autoupdate"]
        elif shutil.which("ngrok"):
            cmd = ["ngrok", "http", str(port), "--log", "stdout"]
        else:
            return None
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True)
        threading.Thread(target=self._watch, daemon=True).start()
        for _ in range(60):
            if self.url:
                os.environ["PEGASUS_PUBLIC_URL"] = self.url
                break
            threading.Event().wait(0.5)
        return self.url

    def _watch(self) -> None:
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            m = URL_RE.search(line)
            if m and not self.url:
                self.url = m.group(0)

    def stop(self) -> None:
        if self.proc:
            self.proc.terminate()
            self.proc = None
        self.url = None
        os.environ.pop("PEGASUS_PUBLIC_URL", None)
