#!/usr/bin/env python3
"""Render per-tool agent adapters from skills/agents.yaml. --check compares."""
import json, sys
from pathlib import Path
import yaml

SRC, MAKE = Path("skills/agents.yaml"), Path("Makefile")
TOOLS = ("opencode", "mimocode", "zcode", "openfable", "zfable")
WORKFLOWS = ("phase-execute", "gate-run", "map-complete",
             "module-scaffold", "handoff-repair", "blocked-recovery")
GATES = {f"G{i}" for i in range(1, 25)}


def targets():
    if not MAKE.exists():
        return set()
    out = set()
    for line in MAKE.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("\t", "#", ".")) and ":" in line:
            out.add(line.split(":")[0].strip())
    return out


def render(spec):
    known = targets()
    missing = {c["make"] for c in spec["commands"]} - known
    if missing:
        sys.exit(f"PRECONDITION: unknown make targets {sorted(missing)}")
    for agent in spec["agents"]:
        if not agent.get("may") or not agent.get("may_not"):
            sys.exit(f"{agent['id']}: may and may_not are required")
        if agent["max_steps"] > 8:
            sys.exit(f"{agent['id']}: max_steps above 8")
        if agent["terminal_gate"] not in GATES:
            sys.exit(f"{agent['id']}: unknown terminal gate")
    for skill in spec.get("skills", []):
        if not Path(f"skills/{skill}.md").exists():
            sys.exit(f"missing skills/{skill}.md")
    out = {}
    for tool in TOOLS:
        base = f".{tool}-skills"
        out[f"{base}/skill.json"] = json.dumps({
            "name": "pegasus-gates", "version": "1.0.0",
            "description": "Phase, gate, map, handoff and scaffold wrappers",
            "category": "workflow", "trigger": "gates",
            "entry_point": f"{base}/pegasus-gates.json",
            "workflows": [f"{base}/workflows/{w}.json" for w in WORKFLOWS],
            "commands": len(spec["commands"]),
            "installation": f"skill install {base}/skill.json"}, indent=2) + "\n"
        out[f"{base}/pegasus-gates.json"] = json.dumps({
            "name": "pegasus-gates", "version": "1.0.0",
            "commands": [{"name": c["name"], "command": f"/{c['name']}",
                          "make": c["make"], "skill": c["skill"]}
                         for c in spec["commands"]],
            "agents": spec["agents"]}, indent=2) + "\n"
    return out


def main():
    files = render(yaml.safe_load(SRC.read_text(encoding="utf-8")))
    if "--check" in sys.argv:
        bad = [p for p, body in files.items()
               if not Path(p).exists() or Path(p).read_text(encoding="utf-8") != body]
        if bad:
            print("PRECONDITION: adapters drifted:\n  " + "\n  ".join(bad), file=sys.stderr)
            return 3
        print("adapters in sync")
        return 0
    for path, body in files.items():
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(body, encoding="utf-8")
    print(f"wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
