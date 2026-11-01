"""Hash-pinned, resuming download. Deletes on mismatch."""
import hashlib
import pathlib

import requests

from . import pins

CACHE = pathlib.Path.home() / ".pegasus" / "models"
CHUNK = 1 << 20


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def fetch(repo: str, quant: str) -> pathlib.Path:
    entry = pins.PINS.get((repo, quant))
    if not entry:
        raise pins.IntegrityFail(f"{repo}:{quant} is unpinned")
    dest = CACHE / entry.sha256
    if dest.exists() and sha256(dest) == entry.sha256:
        return dest
    CACHE.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".part")
    with requests.get(entry.url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with part.open("wb") as fh:
            for block in r.iter_content(CHUNK):
                fh.write(block)
    if sha256(part) != entry.sha256:
        part.unlink()
        raise pins.IntegrityFail(repo)
    part.rename(dest)
    return dest
