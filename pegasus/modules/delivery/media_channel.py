"""Media: photo / media-file delivery handoff (MMS-style)."""
from pathlib import Path

from .adapter import Adapter


class Media(Adapter):
    channel, kinds = "media", frozenset({"photo", "apk", "pdf"})

    def deliver(self, kind, target, body):
        # target is a phone number or contact handle
        path = body.get("path")
        if not path:
            return {"error": "no media path supplied",
                    "note": "media delivery requires body.path"}
        p = Path(path)
        if not p.exists():
            return {"error": f"media file not found: {path}"}
        size_mb = p.stat().st_size / 1e6
        return {"media": target, "file": str(p), "size_mb": round(size_mb, 2),
                "mime": body.get("mime") or "application/octet-stream",
                "note": "send the file to target over MMS/media channel; link fallback included",
                "link": self.link(body)}
