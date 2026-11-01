"""Turn output -> candidate memories. Writes are candidates, never commits."""
import re

RULES = [
    ("host_os", r"SDK (\d+)|Android (\d+)", lambda m: f"sdk={m.group(1) or m.group(2)}"),
    ("host_model", r"ro\.product\.model:\s*(\S+)", lambda m: m.group(1)),
    ("creds_found", r"(\d+) (?:credentials|passwords)", lambda m: m.group(1)),
    ("module_fail", r"fail (\w+): (.+)", lambda m: f"{m.group(1)}: {m.group(2)[:80]}"),
]
WEIGHT = {"host_os": 0.7, "host_model": 0.6, "creds_found": 0.8, "module_fail": 0.5}


def candidates(run_id: str, text: str, verdict: str, case_id: str | None) -> list[dict]:
    out = []
    for kind, pattern, build in RULES:
        for m in re.finditer(pattern, text, re.M):
            out.append({"kind": kind, "value": build(m), "importance": WEIGHT[kind],
                        "source": f"run:{run_id}", "case_id": case_id,
                        "verdict": verdict})
    for cmd in re.findall(r"^\s*([a-z][\w.-]+ .{4,120})$", text, re.M)[:10]:
        out.append({"kind": "proc", "signature": _sig(cmd), "command": cmd,
                    "importance": 0.6, "source": f"run:{run_id}", "case_id": case_id,
                    "verdict": verdict})
    return out[:40]


def _sig(cmd: str) -> str:
    parts = cmd.split()
    return " ".join([parts[0]] + ["<a>" if not p.startswith("-") else p
                                  for p in parts[1:4]])
