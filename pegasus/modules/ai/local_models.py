"""Legacy shim so /api/models/* keeps working."""
import pathlib

from . import catalog

MODELS = pathlib.Path.home() / ".pegasus" / "models"


def platform_tier() -> str:
    return "mlx" if catalog.os_key().startswith("macos") else "gguf"


def installed() -> list[dict]:
    if not MODELS.exists():
        return []
    return [{"file": p.name, "gb": round(p.stat().st_size / 1e9, 2)}
            for p in sorted(MODELS.glob("*.gguf"))]


def installed_default() -> str | None:
    from . import providers
    return providers.load().get("plannerModel")
