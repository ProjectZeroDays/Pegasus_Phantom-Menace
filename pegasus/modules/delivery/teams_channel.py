"""Teams connector card. Link only."""
import os

import requests

from .adapter import Adapter


class Teams(Adapter):
    channel, kinds = "teams", frozenset({"link", "pdf", "photo"})

    def deliver(self, kind, target, body):
        hook = os.environ.get("PEGASUS_TEAMS_WEBHOOK") or target
        card = {"type": "message", "attachments": [{
            "contentType": "application/vnd.microsoft.card.hero",
            "content": {"title": body.get("label", "Document"),
                        "text": body.get("message", ""),
                        "potentialAction": [{"type": "OpenUri", "name": "Open",
                                             "targets": [{"os": "default",
                                                          "uri": self.link(body)["link"]}]}]}}]}
        return {"sent": requests.post(hook, json=card, timeout=30).status_code}
