"""Slack: webhook text, external upload for files."""
import os
import pathlib

import requests

from .adapter import Adapter


class Slack(Adapter):
    channel, kinds, max_mb = "slack", frozenset({"link", "pdf", "photo"}), 20

    def deliver(self, kind, target, body):
        hook = os.environ.get("PEGASUS_SLACK_WEBHOOK")
        token = os.environ.get("SLACK_TOKEN")
        if kind == "link" or not (hook and token):
            text = f"{body.get('message', 'Document')} {self.link(body)['link']}"
            return {"sent": requests.post(hook, json={"text": text}, timeout=30).status_code}
        path = pathlib.Path(body["path"])
        self.guard(body["path"])
        up = requests.post("https://slack.com/api/files.getUploadURLExternal",
                           headers={"Authorization": f"Bearer {token}"},
                           data={"filename": path.name, "length": path.stat().st_size},
                           timeout=30).json()
        requests.post(up["upload_url"], data=path.read_bytes(), timeout=120)
        done = requests.post("https://slack.com/api/files.completeUploadExternal",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"files": [{"id": up["file_id"], "title": path.name}],
                                   "channel_id": target}, timeout=30).json()
        return {"sent": done.get("ok"), "via": "external_upload"}
