"""llama.cpp backend. Constrained calls use /completion (llama.cpp#29006)."""
import asyncio
import os
import shutil
import sys

import requests

from .. import provision
from .base import Backend, GenRes
from .util import detect_gpu, free_port, physical_cores

GPU_FLAGS = {"cuda": ["-ngl", "99", "-fa", "on"], "rocm": ["-ngl", "99", "-fa", "on"],
             "vulkan": ["-ngl", "99"], "cpu": ["--mlock", "--no-mmap", "-b", "256"]}


class LlamaCpp(Backend):
    name = "llamacpp"

    def __init__(self) -> None:
        self.proc = None
        self.port = 0
        self.repo = ""
        self.bin = shutil.which("llama-server") or shutil.which("llama-server.exe") or ""

    async def load(self, repo: str, quant: str, ctx: int) -> None:
        if not self.bin:
            raise RuntimeError("llama-server not on PATH")
        self.repo = repo
        self.model = provision.fetch(repo, quant)
        self.port = free_port()
        self.proc = await asyncio.create_subprocess_exec(
            self.bin, "-m", str(self.model), "-c", str(ctx), "-t", str(physical_cores()),
            "--cache-type-k", "q8_0", "--cache-type-v", "q8_0", *GPU_FLAGS[detect_gpu()],
            "--host", "127.0.0.1", "--port", str(self.port),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)

    async def health(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def unload(self) -> None:
        if self.proc:
            self.proc.terminate()
            await self.proc.wait()
            self.proc = None

    async def generate(self, prompt, grammar, temp, max_tokens, stop,
                       mode="constrained") -> GenRes:
        if mode == "native" or not grammar:
            body = {"messages": [{"role": "user", "content": prompt}],
                    "temperature": temp, "max_tokens": max_tokens, "stop": stop or []}
            r = requests.post(f"http://127.0.0.1:{self.port}/v1/chat/completions",
                              json=body, timeout=180).json()
            return GenRes(text=r["choices"][0]["message"]["content"],
                          backend=self.name, model=self.repo)
        body = {"prompt": prompt, "temperature": temp, "n_predict": max_tokens,
                "stop": stop or [], "cache_prompt": True, "grammar": grammar}
        r = requests.post(f"http://127.0.0.1:{self.port}/completion",
                          json=body, timeout=180).json()
        return GenRes(text=r.get("content", ""), tokens=r.get("tokens_predicted", 0),
                      backend=self.name, model=self.repo)
