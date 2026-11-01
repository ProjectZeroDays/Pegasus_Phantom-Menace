"""Bridge to opencode/mimocode."""
import json
import os
import pathlib
import shutil
import subprocess

CONFIG = pathlib.Path.home() / ".pegasus" / "agents.json"
BINARIES = {"opencode": "opencode", "mimocode": "mimocode"}
BLANK = {"agent": None, "provider": None, "model": None, "skills": ".openfable-skills"}


def load() -> dict:
    if CONFIG.exists():
        try:
            return {**BLANK, **json.loads(CONFIG.read_text())}
        except json.JSONDecodeError:
            pass
    return dict(BLANK)


def save(cfg: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2))


def available() -> dict:
    return {k: bool(shutil.which(v)) for k, v in BINARIES.items()}


def dispatch(prompt: str, cwd: str = ".") -> dict:
    cfg = load()
    agent = cfg.get("agent")
    if not agent:
        raise RuntimeError("no agent selected")
    binary = shutil.which(BINARIES[agent])
    if not binary:
        raise RuntimeError(f"{agent} not installed")
    env = os.environ.copy()
    env["OPENFABLE_SKILLS"] = cfg["skills"]
    proc = subprocess.run([binary, "run", "--non-interactive", prompt], cwd=cwd,
                          env=env, capture_output=True, text=True, timeout=900)
    return {"agent": agent, "code": proc.returncode, "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-4000:]}
