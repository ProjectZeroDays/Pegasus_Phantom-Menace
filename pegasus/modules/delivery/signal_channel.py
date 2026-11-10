"""Signal: signal.me / link handoff; no real messenger API without registration."""
from urllib.parse import quote

from .adapter import Adapter


class Signal(Adapter):
    channel, kinds = "signal", frozenset({"link", "apk", "pdf"})

    def deliver(self, kind, target, body):
        message = body.get("message") or "Document"
        link = self.link(body)
        return {"signal": f"https://signal.me/#ru/?q={quote(target)}&s={quote(message)}",
                "link": link,
                "note": "Signal requires the target to have Signal installed; link fallback included"}
