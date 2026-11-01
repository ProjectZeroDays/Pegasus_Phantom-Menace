"""Remote backend. Used on phones and as the cross-host fallback."""
import requests

from .base import Backend, GenRes


class Remote(Backend):
    name = "remote"

    def __init__(self) -> None:
        self.base = ""

    async def load(self, repo: str, quant: str, ctx: int) -> None:
        import os
        self.base = os.environ.get("PEGASUS_REMOTE_AI", "")
        if not self.base:
            raise RuntimeError("PEGASUS_REMOTE_AI unset")

    async def health(self) -> bool:
        try:
            return requests.get(f"{self.base}/api/health", timeout=5).ok
        except requests.RequestException:
            return False

    async def unload(self) -> None:
        return None

    async def generate(self, prompt, grammar, temp, max_tokens, stop,
                       mode="constrained") -> GenRes:
        r = requests.post(f"{self.base}/api/ai/generate",
                          json={"prompt": prompt, "grammar": grammar, "temp": temp,
                                "max_tokens": max_tokens, "stop": stop}, timeout=180)
        r.raise_for_status()
        data = r.json()["data"]
        return GenRes(**data)
