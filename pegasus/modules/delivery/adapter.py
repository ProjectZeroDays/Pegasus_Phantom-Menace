"""Adapter contract. Unsupported kinds downgrade to link."""
import pathlib
from abc import ABC, abstractmethod

from pegasus.core.config import public_url


class Adapter(ABC):
    channel = ""
    kinds: frozenset[str] = frozenset({"link"})
    js_capable = False
    max_mb = 25

    @abstractmethod
    def deliver(self, kind: str, target: str, body: dict) -> dict: ...

    def link(self, body: dict) -> dict:
        from . import landing
        token = landing.mint({"pdf": body.get("pdf_url"), "apk": body.get("apk_url"),
                              "photo": body.get("photo_url")})
        return {"link": f"{public_url()}/l/{token}"}

    def guard(self, path: str) -> None:
        if pathlib.Path(path).stat().st_size > self.max_mb * 1e6:
            raise ValueError(f"{self.channel} caps at {self.max_mb} MB")
