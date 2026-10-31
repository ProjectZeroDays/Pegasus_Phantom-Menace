#!/usr/bin/env python3
"""NL → slash-command translator."""
from __future__ import annotations
import json


SYSTEM = """You translate operator intent into one Pegasus slash command.
Reply with JSON only: {"command": "/name arg", "confidence": 0.0-1.0, "why": "short", "args": ["a","b"]}.
Available commands: {commands}
If nothing fits, return {"command": null, "confidence": 0, "why": "..."}."""


def translate(text: str, commands: list[str]) -> dict:
    prompt = SYSTEM.replace("{commands}", ", ".join(sorted(commands)))
    try:
        from pegasus.modules.ai.router import Router
        raw = Router().complete(prompt, text, json_mode=True)
    except Exception:
        # deterministic keyword fallback
        return _fallback(text, commands)
    try:
        out = json.loads(raw)
        if isinstance(out.get("command"), str):
            out["command"] = out["command"].lstrip("/")
        return out
    except Exception:
        return _fallback(text, commands)


def _fallback(text: str, commands: list[str]) -> dict:
    """Keyword match so NL still works without an AI key."""
    t = (text or "").lower()
    table = {
        "device": "devices", "devices": "devices", "list": "devices",
        "scan": "cve-scan", "cve": "cve-scan", "vulnerab": "cve-scan",
        "zero-click": "access-zero-click", "zero click": "access-zero-click",
        "autonomous": "access-autonomous", "auto": "access-autonomous",
        "vector": "access-vectors", "vectors": "access-vectors",
        "payload": "payload-factory", "exploit": "access-vectors",
        "wifi": "wifi", "network": "network-scan",
        "app": "app-inventory", "apps": "app-inventory",
        "sms": "sms", "message": "sms", "text": "sms",
        "call": "call-log", "calls": "call-log",
        "contact": "contacts", "contacts": "contacts",
        "location": "last-location", "where": "last-location",
        "photo": "photo", "screenshot": "screen-capture", "camera": "camera-capture",
        "password": "passgen", "wordlist": "passgen",
        "report": "report", "status": "status", "health": "status",
    }
    for needle, cmd in table.items():
        if needle in t and cmd in commands:
            return {"command": cmd, "confidence": 0.6, "why": f"keyword '{needle}'", "args": []}
    return {"command": None, "confidence": 0.0, "why": "no keyword match", "args": []}
