"""System-prompt A/B."""
VARIANTS = ["baseline", "terse", "reference_first"]
_counter: dict[str, int] = {}


def next_variant(role: str) -> str:
    n = _counter.get(role, 0)
    _counter[role] = n + 1
    return VARIANTS[n % len(VARIANTS)]
