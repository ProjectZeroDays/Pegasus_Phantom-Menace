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

# Workflow definitions referenced by skill.json. Each step is (command, make
# target, description) and must line up with the commands declared in
# skills/agents.yaml, otherwise the manifest advertises files that do not exist.
WORKFLOWS_SPEC = {
    "phase-execute": (
        "Run a phase end to end: prerequisites, gate, then refresh the map.",
        [("phase", "require", "Enter the phase and load its prerequisites"),
         ("ready", "ready-check", "Confirm definition-of-ready before work starts"),
         ("gate", "gate", "Run the phase terminal gate"),
         ("map", "map", "Refresh the plan map once the phase completes")],
    ),
    "gate-run": (
        "Run a single gate and audit the surface it touched.",
        [("gate", "gate", "Run the requested gate"),
         ("audit", "audit", "Audit the module surface the gate inspected")],
    ),
    "map-complete": (
        "Regenerate the plan map and confirm every item has an owner.",
        [("map", "map", "Regenerate the plan map from tracked files"),
         ("audit", "audit", "Confirm every mapped item has an owner")],
    ),
    "module-scaffold": (
        "Scaffold a module, audit it, then record the handoff.",
        [("module-new", "module-new", "Scaffold the module skeleton"),
         ("audit", "audit", "Audit the new module against the manifest"),
         ("handoff", "handoff", "Record the handoff note")],
    ),
    "handoff-repair": (
        "Rewrite a stale handoff and capture anything blocked.",
        [("handoff", "handoff", "Rewrite the handoff from the current tree"),
         ("blocked", "blocked", "Capture blocked items found while repairing")],
    ),
    "blocked-recovery": (
        "Record a blocked item, then audit for collateral drift.",
        [("blocked", "blocked", "Record the blocked item and its owner"),
         ("audit", "audit", "Audit for collateral drift")],
    ),
}

assert tuple(WORKFLOWS_SPEC) == WORKFLOWS, "WORKFLOWS and WORKFLOWS_SPEC drifted"


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
        for wf, (desc, steps) in WORKFLOWS_SPEC.items():
            unknown = {make for _, make, _ in steps} - known
            if unknown:
                sys.exit(f"PRECONDITION: workflow {wf} uses unknown make "
                         f"targets {sorted(unknown)}")
            out[f"{base}/workflows/{wf}.json"] = json.dumps({
                "workflow": f"pegasus-{wf}", "version": "1.0.0",
                "description": desc,
                "steps": [{"step": i, "command": f"/{name}", "make": make,
                           "description": text}
                          for i, (name, make, text) in enumerate(steps, 1)],
                "triggers": [wf],
                "output": ".pegasus/reports/",
            }, indent=2) + "\n"
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
