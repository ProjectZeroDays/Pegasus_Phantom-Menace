"""MLX backend. Grammar support is probed, not assumed."""
import asyncio
import os
import sys

import requests

from .. import provision
from .base import Backend, GenRes
from .util import free_port


class Mlx(Backend):
    name = "mlx"

    def __init__(self) -> None:
        self.proc = None
        self.port = 0
        self.repo = ""
        self._grammar: bool | None = None

    async def load(self, repo: str, quant: str, ctx: int) -> None:
        self.repo = repo
        path = provision.fetch(repo, "mlx")
        if not path.is_dir():
            raise RuntimeError("mlx needs a converted repo, not a .gguf")
        self.port = free_port()
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "mlx_lm.server", "--model", str(path),
            "--host", "127.0.0.1", "--port", str(self.port),
            env={**os.environ, "MLX_METAL_PREWARM": "1"},
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        self._grammar = self._probe_grammar()

    def _probe_grammar(self) -> bool:
        try:
            r = requests.post(f"http://127.0.0.1:{self.port}/v1/completions",
                              json={"prompt": "x", "max_tokens": 8,
                                    "grammar": 'root ::= "a"'}, timeout=30).json()
            return r.get("text", "").strip().startswith("a")
        except requests.RequestException:
            return False

    def supports_grammar(self) -> bool:
        return bool(self._grammar)

    async def health(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def unload(self) -> None:
        if self.proc:
            self.proc.terminate()
            await self.proc.wait()
            self.proc = None

    async def generate(self, prompt, grammar, temp, max_tokens, stop,
                       mode="constrained") -> GenRes:
        body = {"prompt": prompt, "temperature": temp, "max_tokens": max_tokens,
                "stop": stop or []}
        if grammar and self.supports_grammar():
            body["grammar"] = grammar
        r = requests.post(f"http://127.0.0.1:{self.port}/v1/completions",
                          json=body, timeout=180).json()
        return GenRes(text=r.get("text", ""), backend=self.name, model=self.repo)
