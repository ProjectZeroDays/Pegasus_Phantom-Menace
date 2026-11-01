"""Cloud provider keys. Stored at 0600."""
import json
import os
import pathlib

CONFIG = pathlib.Path.home() / ".pegasus" / "providers.json"
REGISTRY = {
    "openai": {"label": "OpenAI", "env": "OPENAI_API_KEY", "kind": "cloud"},
    "anthropic": {"label": "Anthropic", "env": "ANTHROPIC_API_KEY", "kind": "cloud"},
    "groq": {"label": "Groq", "env": "GROQ_API_KEY", "kind": "cloud"},
    "openrouter": {"label": "OpenRouter", "env": "OPENROUTER_API_KEY", "kind": "cloud"},
    "venice": {"label": "Venice", "env": "VENICE_API_KEY", "kind": "cloud"},
    "deepseek": {"label": "DeepSeek", "env": "DEEPSEEK_API_KEY", "kind": "cloud"},
    "local": {"label": "Local model", "env": None, "kind": "local"}}
BLANK = {"keys": {}, "default": None, "fallback": None, "plannerModel": None,
         "coderModel": None}


def load() -> dict:
    if CONFIG.exists():
        try:
            return {**BLANK, **json.loads(CONFIG.read_text())}
        except json.JSONDecodeError:
            pass
    return dict(BLANK)


def save(data: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, indent=2))
    os.chmod(CONFIG, 0o600)


def key_for(name: str) -> str | None:
    env = REGISTRY[name]["env"]
    return load().get("keys", {}).get(name) or (os.environ.get(env) if env else None)


def configured() -> list[str]:
    return sorted({n for n in REGISTRY if key_for(n)})


def needs_setup() -> bool:
    return not configured() and not load().get("default")
