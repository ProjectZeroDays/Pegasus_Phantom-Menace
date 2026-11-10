"""NFC: NDEF URI record payload; read-only generation, no silent install."""
from urllib.parse import quote

from .adapter import Adapter


class NFC(Adapter):
    channel, kinds = "nfc", frozenset({"link"})

    def deliver(self, kind, target, body):
        # target is the NFC tag/device identifier (operator-supplied)
        link = self.link(body)
        uri = body.get("url") or link["link"] if isinstance(link, dict) else link
        return {"nfc": target, "ndef": f"https://nfc.org/ndef?uri={quote(uri)}",
                "link": link,
                "note": "write the NDEF URI to a tag; target must tap to open"}
