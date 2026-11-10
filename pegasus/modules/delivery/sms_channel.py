"""SMS: short-link landing or mock-gateway send."""
from urllib.parse import quote

from .adapter import Adapter


class SMS(Adapter):
    channel, kinds = "sms", frozenset({"link", "apk", "pdf", "photo"})

    def deliver(self, kind, target, body):
        message = body.get("message") or "Document"
        if kind == "link":
            return self.link(body)
        gateway = body.get("sms_gateway")
        if gateway:
            return {
                "sms": f"{gateway}/send?to={quote(target)}&text={quote(message)}",
                "link": self.link(body),
            }
        # Defensive: no real SMS provider configured, fall back to link
        return {"sms": None, "link": self.link(body),
                "note": "no sms_gateway configured; link fallback used"}
