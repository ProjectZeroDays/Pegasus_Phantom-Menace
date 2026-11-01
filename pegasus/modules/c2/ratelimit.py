"""Fixed-window limiter keyed by an arbitrary string."""
import time

WINDOW, LIMIT = 60.0, 30
_state: dict[str, list[float]] = {}


def allow(key: str, limit: int = LIMIT) -> bool:
    now = time.time()
    hits = _state.setdefault(key, [])
    hits[:] = [t for t in hits if now - t < WINDOW]
    if len(hits) >= limit:
        return False
    hits.append(now)
    return True


def forget(key: str) -> None:
    _state.pop(key, None)
