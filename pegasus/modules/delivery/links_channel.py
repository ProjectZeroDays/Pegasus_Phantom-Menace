"""Links: short-link / landing-page delivery (generic carrier)."""
from urllib.parse import quote

from .adapter import Adapter


class Links(Adapter):
    channel, kinds = "links", frozenset({"link"})

    def deliver(self, kind, target, body):
        message = body.get("message") or "Document"
        custom = body.get("short_link")
        base = custom or self.link(body).get("link", "")
        return {"links": target, "url": base,
                "sms_fallback": f"sms:{quote(target)}?body={quote(message)}",
                "note": "generic short-link carrier; target opens the link manually"}
