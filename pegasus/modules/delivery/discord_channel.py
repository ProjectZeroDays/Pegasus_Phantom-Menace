"""Discord webhook."""
import os

import requests

from .adapter import Adapter


class Discord(Adapter):
    channel, kinds, max_mb = "discord", frozenset({"link", "apk", "pdf", "photo"}), 10

    def deliver(self, kind, target, body):
        hook = os.environ.get("PEGASUS_DISCORD_WEBHOOK") or target
        if kind == "link":
            return {"sent": requests.post(hook, json={
                "content": f"{body.get('message', 'Document')} {self.link(body)['link']}"},
                timeout=30).status_code}
        self.guard(body["path"])
        with open(body["path"], "rb") as fh:
            r = requests.post(hook, data={"content": body.get("message", "")[:1800]},
                              files={"file": fh}, timeout=120)
        r.raise_for_status()
        return {"sent": r.status_code, "via": "webhook"}
