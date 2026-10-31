#!/usr/bin/env python3
"""AI provider router — picks default → fallback → first configured."""
from __future__ import annotations
import json


class Router:
    _instance = None

    @classmethod
    def invalidate(cls):
        cls._instance = None

    def __init__(self):
        from pegasus.modules.ai import providers
        data = providers.load()
        self.default = data.get("default")
        self.fallback = data.get("fallback")
        self.keys = data.get("keys", {})
        self.local_model = data.get("localModel")

    def _pick(self) -> str | None:
        if self.default and (self.default == "local" or self.keys.get(self.default)):
            return self.default
        if self.fallback and (self.fallback == "local" or self.keys.get(self.fallback)):
            return self.fallback
        for name in self.keys:
            return name
        return None

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        """Route completion through the configured provider or local model."""
        pick = self._pick()
        if pick == "local" or (self.local_model and not self.keys):
            return self._complete_local(system, user, json_mode)
        if not pick:
            raise RuntimeError("no AI provider configured — run setup")
        key = self.keys.get(pick)
        if not key:
            from pegasus.modules.ai.providers import REGISTRY
            import os
            env = REGISTRY.get(pick, {}).get("env")
            key = os.environ.get(env or "", "")
        return self._complete_cloud(pick, key, system, user, json_mode)

    def _complete_cloud(self, provider: str, key: str, system: str, user: str, json_mode: bool) -> str:
        import requests
        if provider in ("openai", "groq", "deepseek", "openrouter", "venice"):
            base = {
                "openai": "https://api.openai.com/v1",
                "groq": "https://api.groq.com/openai/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "openrouter": "https://openrouter.ai/api/v1",
                "venice": "https://api.venice.ai/api/v1",
            }[provider]
            r = requests.post(f"{base}/chat/completions", json={
                "model": "gpt-4o-mini" if provider == "openai" else "llama-3.1-8b-instruct",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **({"response_format": {"type": "json_object"}} if json_mode else {}),
            }, headers={"Authorization": f"Bearer {key}"}, timeout=60)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        if provider == "anthropic":
            r = requests.post("https://api.anthropic.com/v1/messages", json={
                "model": "claude-3-5-haiku-latest", "max_tokens": 512, "system": system,
                "messages": [{"role": "user", "content": user}],
            }, headers={"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout=60)
            r.raise_for_status()
            return r.json()["content"][0]["text"]
        if provider == "google":
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
                json={"contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}]}, timeout=60)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        if provider == "mistral":
            r = requests.post("https://api.mistral.ai/v1/chat/completions", json={
                "model": "mistral-small-latest",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            }, headers={"Authorization": f"Bearer {key}"}, timeout=60)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        raise RuntimeError(f"provider {provider} not routable")

    def _complete_local(self, system: str, user: str, json_mode: bool) -> str:
        import requests
        from pegasus.modules.ai import local_models
        # already serving?
        port = getattr(local_models, "_RUNNING", {}).get("port")
        base = f"http://127.0.0.1:{port or 8081}/v1"
        try:
            r = requests.post(f"{base}/chat/completions", json={
                "model": self.local_model or "local",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                **({"response_format": {"type": "json_object"}} if json_mode else {}),
            }, timeout=120)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception:
            # no local server — deterministic fallback keeps NL usable
            raise
