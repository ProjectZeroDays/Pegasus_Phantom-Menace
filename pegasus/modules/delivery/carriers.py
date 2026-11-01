"""Routing guard plus dispatch. Unsupported kinds downgrade to link."""
from . import adapters, legacy, twilio_channel

PDF_HOSTILE = ("att", "rogers", "fido", "telus")


def carrier_for(channel: str, requested: str, network: str | None = None) -> str:
    if channel in ("sms", "mms"):
        return "link"
    if channel == "messenger" and requested == "pdf":
        return "pdf_lure"
    if requested == "pdf" and network and network.lower() in PDF_HOSTILE:
        return "link"
    return requested


def dispatch(channel: str, kind: str, target: str, body: dict) -> dict:
    network = twilio_channel.carrier_of(target) if target.startswith("+") else None
    kind = carrier_for(channel, kind, network)
    if channel in legacy.LEGACY:
        return {**legacy.dispatch(channel, kind, target, body), "network": network}
    if channel not in adapters.REGISTRY:
        raise KeyError(f"unknown channel {channel}")
    adapter = adapters.get(channel)
    if kind not in adapter.kinds:
        kind = "link"
    return {**adapter.deliver(kind, target, body), "carrier": kind, "network": network}
