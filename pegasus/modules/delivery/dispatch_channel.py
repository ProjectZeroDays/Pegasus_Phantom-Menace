"""Dispatch: router that picks the best available channel for a target."""
from .adapter import Adapter


# Preferred channel order when no explicit channel is requested.
PREFERRED = ("sms", "whatsapp", "telegram", "email", "links")


class Dispatch(Adapter):
    channel, kinds = "dispatch", frozenset({"link", "apk", "pdf", "photo"})

    def deliver(self, kind, target, body):
        requested = body.get("channel")
        # When no explicit channel, walk preferred order and return the first
        # candidate with a resolved link payload.
        candidates = [requested] if requested else list(PREFERRED)
        for ch in candidates:
            if ch == self.channel:
                continue  # avoid self-loop
            try:
                from .adapters import get as _get
                adapter = _get(ch)
                if kind in adapter.kinds:
                    result = adapter.deliver(kind, target, body)
                    result["via_dispatch"] = ch
                    return result
            except Exception:  # noqa: BLE001 -- channel missing/unavailable, try next
                continue
        # Final fallback: plain link
        return {"dispatch": None, "link": self.link(body),
                "note": "no carrier resolved; link fallback used"}
