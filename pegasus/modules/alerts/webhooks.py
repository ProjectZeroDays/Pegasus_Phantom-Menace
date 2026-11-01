"""Slack / Teams / Discord fan-out."""
import os

import requests

KINDS = {"slack": lambda t, b: {"text": f"*{t}*\n{b}"},
         "teams": lambda t, b: {"title": t, "text": b},
         "discord": lambda t, b: {"content": f"**{t}**\n{b}"}}


def send(title: str, body: str) -> dict:
    out = {}
    for kind, build in KINDS.items():
        url = os.environ.get(f"PEGASUS_{kind.upper()}_WEBHOOK")
        if not url:
            continue
        try:
            out[kind] = requests.post(url, json=build(title, body), timeout=15).status_code
        except requests.RequestException as exc:
            out[kind] = str(exc)
    return out
