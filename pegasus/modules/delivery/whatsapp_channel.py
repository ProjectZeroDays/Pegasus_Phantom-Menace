"""WhatsApp: wa.me link, Cloud API when a token exists."""
import os
import pathlib
import re
from urllib.parse import quote

import requests

from .adapter import Adapter

GRAPH = "https://graph.facebook.com/v19.0"


def _digits(number: str) -> str:
    return re.sub(r"\D", "", number)


class WhatsApp(Adapter):
    channel, kinds = "whatsapp", frozenset({"link", "apk", "pdf", "photo"})

    def deliver(self, kind, target, body):
        if kind == "link" or not os.environ.get("WHATSAPP_TOKEN"):
            return {"link": f"https://wa.me/{_digits(target)}?text="
                            f"{quote(body.get('message') or 'Document')}"}
        return self._cloud(kind, target, body)

    def _cloud(self, kind, target, body):
        phone = os.environ["WHATSAPP_PHONE_ID"]
        with open(body["path"], "rb") as fh:
            up = requests.post(f"{GRAPH}/{phone}/media",
                               headers={"Authorization":
                                        f"Bearer {os.environ['WHATSAPP_TOKEN']}"},
                               files={"file": (pathlib.Path(body["path"]).name, fh)},
                               data={"messaging_product": "whatsapp"}, timeout=120)
        up.raise_for_status()
        r = requests.post(f"{GRAPH}/{phone}/messages",
                          headers={"Authorization":
                                   f"Bearer {os.environ['WHATSAPP_TOKEN']}"},
                          json={"messaging_product": "whatsapp", "to": _digits(target),
                                "type": "document",
                                "document": {"id": up.json()["id"]}}, timeout=60)
        r.raise_for_status()
        return {"sent": r.json(), "via": "cloud_api"}
