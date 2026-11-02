"""Host model. A host is any target: phone, laptop, router, camera, PLC, drone."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from core.caps import Cap


class HostKind(str, Enum):
    ANDROID = "android"; IOS = "ios"; WINDOWS = "windows"; LINUX = "linux"
    MACOS = "macos"; IOT = "iot"; ROUTER = "router"; CAMERA = "camera"
    ICS = "ics"; DRONE = "drone"; SENSOR = "sensor"


class Trust(str, Enum):
    UNVERIFIED = "unverified"   # discovery only; read caps
    PINNED = "pinned"           # key or pairing record; non-destructive
    VERIFIED = "verified"       # signed attestation; destructive allowed
    DEMOTED = "demoted"         # conformance failure; drops one level


@dataclass
class Host:
    id: str
    kind: HostKind
    os_hint: str | None = None
    transports: list[str] = field(default_factory=list)
    caps: set[Cap] = field(default_factory=set)
    reachable_via: str | None = None
    trust: Trust = Trust.UNVERIFIED

    def allows(self, caps: set[Cap]) -> bool:
        return caps <= self.caps
