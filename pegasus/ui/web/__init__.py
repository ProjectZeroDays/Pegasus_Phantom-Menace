"""Web GUI package for Pegasus Phantom Menace v2."""

from .backend.app import create_app  # noqa: F401
from .server import main as serve  # noqa: F401

__all__ = ["create_app", "serve"]
