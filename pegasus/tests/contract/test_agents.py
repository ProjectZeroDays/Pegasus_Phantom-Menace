"""Contract: agent adapters match skills/agents.yaml and stay bounded."""
import json
from pathlib import Path

import pytest
import yaml

TOOLS = ("opencode", "mimocode", "zcode", "openfable", "zfable")
WORKFLOWS = ("phase-execute", "gate-run", "map-complete",
             "module-scaffold", "handoff-repair", "blocked-recovery")
GATES = {f"G{i}" for i in range(1, 25)}


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(Path("skills/agents.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def targets():
    out = set()
    for line in Path("Makefile").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("\t", "#", ".")) and ":" in line:
            out.add(line.split(":")[0].strip())
    return out


@pytest.mark.parametrize("tool", TOOLS)
def test_adapter_files_exist(tool):
    base = Path(f".{tool}-skills")
    assert (base / "skill.json").exists()
    assert (base / "pegasus-gates.json").exists()
    for name in WORKFLOWS:
        assert (base / "workflows" / f"{name}.json").exists()


@pytest.mark.parametrize("tool", TOOLS)
def test_adapter_parses(tool):
    for path in Path(f".{tool}-skills").rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_commands_map_to_real_targets(spec, targets):
    for cmd in spec["commands"]:
        assert cmd["make"] in targets, f"/{cmd['name']} -> {cmd['make']}"


def test_agents_declare_scope(spec):
    for agent in spec["agents"]:
        assert agent["may"], f"{agent['id']} has no may"
        assert agent["may_not"], f"{agent['id']} has no may_not"


def test_agents_are_bounded(spec):
    for agent in spec["agents"]:
        assert agent["max_steps"] <= 8, f"{agent['id']} exceeds 8 steps"
        assert agent["terminal_gate"] in GATES, f"{agent['id']} has a bad gate"


def test_agents_do_not_edit_the_guard(spec):
    for agent in spec["agents"]:
        joined = " ".join(agent["may"])
        assert "edit scripts/" not in joined, f"{agent['id']} may edit scripts/"
        assert "edit build/phases.yaml" not in joined, f"{agent['id']} may edit phases"


def test_skills_referenced_exist(spec):
    for skill in spec["skills"]:
        assert Path(f"skills/{skill}.md").exists(), f"missing skills/{skill}.md"


def test_adapters_identical_across_tools():
    # Bodies embed the tool's own install path, so normalise that before
    # comparing; everything else must be byte-identical.
    for name in ("skill.json", "pegasus-gates.json"):
        bodies = {t: Path(f".{t}-skills/{name}").read_text(encoding="utf-8")
                  .replace(f".{t}-skills", "%BASE%") for t in TOOLS}
        assert len(set(bodies.values())) == 1, f"{name} differs across tools"


def test_adapters_in_sync():
    import subprocess
    import sys
    code = subprocess.run([sys.executable, "scripts/emit_agents.py", "--check"],
                          capture_output=True).returncode
    assert code == 0, "run: make agents"
