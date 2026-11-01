"""Promotion gate. Three conditions, all must hold."""
import json
import pathlib

GATE = pathlib.Path.home() / ".pegasus" / "gate.json"


def evaluate(candidate: dict, baseline: dict) -> tuple[bool, str]:
    if candidate["pass_rate"] < baseline["pass_rate"] + 0.03:
        return False, "pass rate"
    if candidate["fail_rate"] > baseline["fail_rate"] + 0.02:
        return False, "fail rate"
    if candidate["p95_ms"] > baseline["p95_ms"] * 1.4:
        return False, "latency"
    return True, "ok"


def record(role: str, candidate: dict, baseline: dict, ok: bool, why: str) -> None:
    data = json.loads(GATE.read_text()) if GATE.exists() else {}
    data[role] = {"candidate": candidate, "baseline": baseline, "ok": ok, "why": why}
    GATE.write_text(json.dumps(data, indent=2))
