"""Generated pin table. Regenerate with scripts/pin_model.py."""
from dataclasses import dataclass


class IntegrityFail(RuntimeError):
    pass


@dataclass(frozen=True)
class Pin:
    url: str
    sha256: str
    size: int
    licence: str


PINS: dict[tuple[str, str], Pin] = {}

try:
    from .pins_data import PINS as _DATA  # noqa: F401
    PINS.update(_DATA)
except ImportError:
    pass
