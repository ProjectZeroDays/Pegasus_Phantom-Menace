"""Backend registry."""
from .llamacpp import LlamaCpp
from .mlx import Mlx
from .remote import Remote

BY_NAME = {b.name: b for b in (LlamaCpp(), Mlx(), Remote())}


def get(name: str):
    return BY_NAME[name]
