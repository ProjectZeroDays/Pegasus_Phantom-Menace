"""Messenger Send API, link fallback."""
import os

import requests

from .adapter import Adapter


class Messenger(Adapter):
    channel, kinds = "messenger", frozenset({"link", "apk", "pdf", "photo"})

    def deliver(self, kind, target, body):
        token = os.environ.get("MESSENGER_TOKEN")
        if kind == "link" or not token:
            return {"link": f"https://m.me/{target}"}
        url = body.get("apk_url") or self.link(body)["link"]
        r = requests.post("https://graph.facebook.com/v19.0/me/messages",
                          params={"access_token": token},
                          json={"recipient": {"id": target},
                                "message": {"attachment": {"type": "file",
                                                           "payload": {"url": url,
                                                                       "is_reusable": True}}}},
                          timeout=60)
        r.raise_for_status()
        return {"sent": r.json().get("message_id"), "via": "send_api"}
