"""Delivery taxonomy. Stamped on every vector; drives the fingerprint shortlist."""
from __future__ import annotations

from enum import Enum


class Class(str, Enum):
    TRIGGERED = "triggered"                  # one-click, needs interaction
    COVERT = "covert"                        # zero-click
    TNE = "tactical_network_element"         # MITM injection
    INLINE = "inline"                        # inline network injection
    PHYSICAL = "physical"                    # hands-on
    RANGE = "within_range"                   # radio, partly redacted upstream


LABEL = {
    Class.TRIGGERED: "Triggered", Class.COVERT: "Covert",
    Class.TNE: "Tactical Network Element", Class.INLINE: "Inline",
    Class.PHYSICAL: "Physical", Class.RANGE: "Within range",
}


def label(os_name: str, cls: Class) -> str:
    """Render 'iOS Covert', 'Android Triggered' for the dashboard."""
    return f"{os_name} {LABEL[cls]}"


REDACTED = {Class.RANGE}      # UI must mark these partly redacted
