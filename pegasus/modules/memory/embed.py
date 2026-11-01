"""Local embeddings via llama.cpp /embedding."""
import hashlib
import math
import os

import requests

MODEL = os.environ.get("PEGASUS_EMBED_MODEL", "bge-small-en-v1.5-q8_0.gguf")
PORT = os.environ.get("PEGASUS_EMBED_PORT", "8082")
_cache: dict[str, list[float]] = {}


def embed(text: str) -> list[float]:
    key = hashlib.sha256(text.encode()).hexdigest()
    if key in _cache:
        return _cache[key]
    r = requests.post(f"http://127.0.0.1:{PORT}/embedding",
                      json={"content": text[:2000], "model": MODEL}, timeout=30)
    r.raise_for_status()
    vec = _norm(r.json()["embedding"])
    _cache[key] = vec
    if len(_cache) > 5000:
        _cache.pop(next(iter(_cache)))
    return vec


def _norm(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]
