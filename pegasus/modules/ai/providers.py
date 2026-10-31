#!/usr/bin/env python3
"""Provider registry and startup wizard for Pegasus v2.1."""
from __future__ import annotations
import json, os, pathlib

CONFIG = pathlib.Path.home() / ".pegasus" / "providers.json"

REGISTRY = {
    "openrouter": {"label":"OpenRouter","env":"OPENROUTER_API_KEY","kind":"cloud"},
    "openai":     {"label":"OpenAI","env":"OPENAI_API_KEY","kind":"cloud"},
    "anthropic":  {"label":"Anthropic","env":"ANTHROPIC_API_KEY","kind":"cloud"},
    "google":     {"label":"Google","env":"GOOGLE_API_KEY","kind":"cloud"},
    "groq":       {"label":"Groq","env":"GROQ_API_KEY","kind":"cloud"},
    "mistral":    {"label":"Mistral","env":"MISTRAL_API_KEY","kind":"cloud"},
    "venice":     {"label":"Venice","env":"VENICE_API_KEY","kind":"cloud"},
    "deepseek":   {"label":"DeepSeek","env":"DEEPSEEK_API_KEY","kind":"cloud"},
    "local":      {"label":"Local model","env":None,"kind":"local"},
}

def load() -> dict:
    if CONFIG.exists():
        try: return json.loads(CONFIG.read_text())
        except Exception: pass
    return {"keys":{},"default":None,"fallback":None}

def save(data: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, indent=2))
    os.chmod(CONFIG, 0o600)

def configured() -> list[str]:
    data = load()
    out = [k for k, v in data.get("keys",{}).items() if v]
    for name, meta in REGISTRY.items():
        if meta["env"] and os.environ.get(meta["env"]):
            out.append(name)
    return sorted(set(out))

def needs_setup() -> bool:
    return not configured() and not load().get("default")
