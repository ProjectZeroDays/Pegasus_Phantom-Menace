#!/usr/bin/env python3
"""Doctor, readiness, gate dispatch and preflight for the phase contract."""
import os, platform, shutil, subprocess, sys
from pathlib import Path

GATE_TARGET = {
    "G1": "setup", "G2": "test", "G3": "integ", "G4": "contract", "G5": "lint",
    "G6": "ui", "G7": "parity", "G8": "dist", "G9": "import",
    "G10": "openapi-snapshot", "G11": "map", "G12": "plan-lint",
    "G13": "handoff-check", "G14": "handoff-guard", "G15": "hooks-check",
    "G16": "bootstrap-check", "G17": "agents-check", "G18": "agents-lint",
    "G19": "conformance", "G20": "modules-lint", "G21": "audit-check",
    "G22": "replay", "G23": "evidence-check", "G24": "eval",
}
REQUIRED_TOOLING = [
    "scripts/handoff.py", "scripts/require.py", "scripts/emit_agents.py",
    "scripts/bootstrap-check.py", "scripts/verify.py", "scripts/openapi_snapshot.py",
    "scripts/module_new.py", "scripts/parity.py", "scripts/version_check.py",
    "scripts/modules_lint.py", "scripts/audit_derive.py", "scripts/caps_matrix.py",
    "scripts/risk_lint.py", "scripts/no_platform_branch.py", "scripts/capability_check.py",
    "scripts/capreg.py", "scripts/caps_consistency.py",
    "pegasus/tests/contract/test_agents.py",
    ".githooks/pre-commit", ".githooks/pre-push", ".githooks/commit-msg",
]


def fail(msg):
    print(f"  FAIL {msg}")
    return 1


def ok(msg):
    print(f"  ok   {msg}")
    return 0


def doctor():
    bad = 0
    bad += ok(f"python {platform.python_version()}") if sys.version_info >= (3, 11) \
        else fail(f"python {platform.python_version()} < 3.11")
    for exe in ("git", "node", "npm"):
        bad += ok(exe) if shutil.which(exe) else fail(f"{exe} not on PATH")
    for exe in ("adb", "make"):
        print(f"  opt  {exe}" if shutil.which(exe) else f"  warn {exe} missing")
    code = subprocess.run([sys.executable, "-c", "import yaml"],
                          capture_output=True).returncode
    bad += ok("pyyaml") if code == 0 else fail("pyyaml missing")
    for rel in REQUIRED_TOOLING:
        bad += ok(rel) if Path(rel).exists() else fail(f"{rel} missing")
    cfg = subprocess.run(["git", "config", "core.hooksPath"],
                         capture_output=True, text=True).stdout.strip()
    bad += ok("hooksPath=.githooks") if cfg == ".githooks" else fail("hooksPath unset — run: make hooks")
    return 1 if bad else 0


def preflight():
    bad = 0
    for rel in ("docs/PLAN.md", "docs/HANDOFF.md", "build/phases.yaml"):
        bad += ok(rel) if Path(rel).exists() else fail(f"{rel} missing")
    return 1 if bad else 0


def ready():
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"],
                            capture_output=True, text=True).stdout.split()
    plan = Path("docs/PLAN.md")
    if not plan.exists():
        return fail("docs/PLAN.md missing")
    text = plan.read_text(encoding="utf-8")
    bad = 0
    for path in staged:
        if path.startswith(("docs/", "scripts/", ".githooks/", "build/")):
            continue
        bad += ok(f"map row: {path}") if path in text else fail(f"no map row for {path}")
    return 1 if bad else 0


def blocked():
    code = subprocess.run([sys.executable, "scripts/require.py", "--lint"],
                          capture_output=True, text=True)
    print(code.stdout.strip() or code.stderr.strip())
    print("classify: exit 3 = precondition, exit 2 = gate, else environment")
    return code.returncode


def gate(gid):
    target = GATE_TARGET.get(gid)
    if not target:
        return fail(f"unknown gate {gid}")
    print(f"  {gid} -> make {target}")
    if not shutil.which("make"):
        return fail("make not on PATH")
    if not Path("Makefile").exists():
        return fail("Makefile missing")
    if f"\n{target}:" not in Path("Makefile").read_text(encoding="utf-8"):
        return fail(f"target {target} absent from Makefile")
    return subprocess.run(["make", target]).returncode


def main():
    args = sys.argv[1:]
    if "--doctor" in args:
        return doctor()
    if "--preflight" in args:
        return preflight()
    if "--ready" in args:
        return ready()
    if "--blocked" in args:
        return blocked()
    if "--gate" in args:
        idx = args.index("--gate")
        if idx + 1 >= len(args):
            return fail("--gate needs an id")
        return gate(args[idx + 1])
    print("usage: verify.py --doctor|--ready|--blocked|--preflight|--gate <id>")
    return 2


if __name__ == "__main__":
    sys.exit(main())
