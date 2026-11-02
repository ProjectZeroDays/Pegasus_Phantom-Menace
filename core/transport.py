"""Transport ABC and probe result. `provides` comes from conformance passes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.caps import Cap
from core.host import Host


class TransportError(Exception):
    pass


class CapUnavailable(TransportError):
    def __init__(self, cap: Cap):
        super().__init__(f"no transport provides {cap}")
        self.cap = cap


@dataclass
class Probe:
    ok: bool
    reason: str = ""
    caps: set[Cap] = field(default_factory=set)

    @classmethod
    def yes(cls) -> "Probe":
        return cls(True)

    @classmethod
    def no(cls, reason: str) -> "Probe":
        return cls(False, reason)

    def cap(self, *caps: Cap) -> "Probe":
        self.caps |= set(caps)
        return self

    def drop(self, *caps: Cap) -> "Probe":
        self.caps -= set(caps)
        return self


class Transport(ABC):
    name: str
    provides: frozenset[Cap]
    cost: int = 50          # lower preferred: adb=10, ssh=20, pivot=60

    @abstractmethod
    async def probe(self, host: Host) -> Probe: ...

    @abstractmethod
    async def open(self, host: Host, lease_id: str) -> "Session": ...
