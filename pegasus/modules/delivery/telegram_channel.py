"""Telegram Bot API."""
import os
from urllib.parse import quote

import requests

from .adapter import Adapter


class Telegram(Adapter):
    channel, kinds, max_mb = "telegram", frozenset({"link", "apk", "pdf", "photo"}), 50

    def deliver(self, kind, target, body):
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        if kind == "link":
            bot = token.split(":")[0]
            return {"link": f"https://t.me/{bot}?start="
                            f"{quote(self.link(body)['link'])}"}
        self.guard(body["path"])
        with open(body["path"], "rb") as fh:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                              data={"chat_id": target,
                                    "caption": body.get("message", "")[:900]},
                              files={"document": fh}, timeout=120)
        r.raise_for_status()
        return {"sent": r.json()["result"]["message_id"], "via": "bot_api"}
