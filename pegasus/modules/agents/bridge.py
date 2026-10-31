#!/usr/bin/env python3
"""Agent bridge — opencode / mimicode / openfable dispatcher."""
from __future__ import annotations
import json, pathlib, shutil, subprocess, os

CONFIG = pathlib.Path.home() / ".pegasus" / "agents.json"
AGENTS = {"opencode":"opencode","mimicode":"mimicode","openfable":"openfable"}

def load() -> dict:
    if CONFIG.exists():
        try: return json.loads(CONFIG.read_text())
        except: pass
    return {"agent": None, "provider": None, "model": None, "skills": ".mimicode-skills"}

def save(d: dict):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(d, indent=2))
    os.chmod(CONFIG, 0o600)

def available() -> dict:
    return {k: bool(shutil.which(v)) for k, v in AGENTS.items()}

def dispatch(prompt: str, cwd: str = ".") -> dict:
    cfg = load()
    agent = cfg.get("agent")
    if not agent or agent not in AGENTS or not shutil.which(AGENTS[agent]):
        return {"agent": agent, "ok": False, "error": f"agent '{agent}' not installed"}
    env = os.environ.copy()
    env["OPENFABLE_SKILLS"] = cfg.get("skills", ".mimicode-skills")
    if cfg.get("provider"): env["PEGASUS_PROVIDER"] = cfg["provider"]
    if cfg.get("model"): env["PEGASUS_MODEL"] = cfg["model"]
    proc = subprocess.run([AGENTS[agent], "run", "--non-interactive", prompt],
                          cwd=cwd, env=env, capture_output=True, text=True, timeout=900)
    return {"agent": agent, "ok": proc.returncode == 0,
            "stdout": proc.stdout[-20000:], "stderr": proc.stderr[-4000:]}
