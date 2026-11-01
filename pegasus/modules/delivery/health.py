"""Channel readiness. link-only means usable without an attachment."""
import os

from . import adapters, legacy

TOKENS = {"whatsapp": "WHATSAPP_TOKEN", "messenger": "MESSENGER_TOKEN",
          "slack": "SLACK_TOKEN"}


def probe(channel: str) -> dict:
    adapter = adapters.REGISTRY.get(channel)
    if not adapter:
        if channel in legacy.LEGACY:
            return {"state": "ok", "kinds": ["link"], "max_mb": 25, "reason": ""}
        return {"state": "missing", "kinds": [], "max_mb": 0, "reason": "no adapter"}
    env = TOKENS.get(channel)
    if env and not os.environ.get(env):
        return {"state": "link-only", "kinds": sorted(adapter.kinds),
                "max_mb": adapter.max_mb, "reason": f"{env} unset"}
    return {"state": "ok", "kinds": sorted(adapter.kinds),
            "max_mb": adapter.max_mb, "reason": ""}


def all_channels() -> dict:
    return {c: probe(c) for c in list(adapters.REGISTRY) + list(legacy.LEGACY)}
