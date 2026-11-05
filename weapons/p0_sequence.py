#!/usr/bin/env python3
"""P0 sequence v4: branch, ignore vendored dirs, commit in groups, run --force, verify.

v4 fixes step 5: after a `git reset` the deletions are worktree-side, so the
prune list is read from both the index and the worktree, and filtered to
root-level paths — the adapter deletions stay with the adapter commit.

v3 fixed two earlier defects:
  * vendored dirs are ignored before staging, so `git add -A -- pegasus/`
    no longer sweeps in node_modules and .pyc files
  * a rejected commit is fatal and reported, not mistaken for "nothing staged"

    python p0_sequence.py --dry-run
    python p0_sequence.py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BRANCH = "P0/plan-and-handoff"
PATCHES = ["patch_v331.py", "patch_v331b.py", "patch_v331c.py"]
BACKUP_IGNORE = "bootstrap.py.v33.*.bak"
VENDOR_IGNORE = ["node_modules/", "__pycache__/", "*.pyc", "*.tsbuildinfo"]

GROUPS = [
    ("P0: bootstrap v33.3 — harness fixes, enum orphan sweep",
     ["bootstrap.py", ".gitignore", "p0_sequence.py"]),
    ("P0: regenerate tooling and adapters at v33.3",
     ["Makefile", "scripts/", "skills/", ".githooks/", ".bootstrap-state",
      ".mimocode-skills/", ".opencode-skills/", ".openfable-skills/",
      ".zcode-skills/", ".zfable-skills/"]),
    ("P0: scaffold, transports, risk register and proof stubs",
     ["core/", "delivery/", "post_exploitation/", "transports/", "risk/",
      "tests/", "pegasus/", "packaging/", "assets/", "builds/"]),
    ("P0: plan and generated handoff",
     ["docs/", "pegsus-mster-plan-v2.md", "append_plan_sections.py"]),
]

EXPECTED_RED = [
    (["scripts/capability_check.py"], "nav still says Dashboard (P6)"),
    (["scripts/no_platform_branch.py"], "no module bodies yet (P11)"),
]

HOOK_CHECKS = [
    (["scripts/handoff.py", "--check"], "handoff in sync"),
    (["scripts/emit_agents.py", "--check"], "adapters in sync"),
    (["scripts/modules_lint.py"], "manifests valid"),
]


def say(msg: str) -> None:
    print(f"\n== {msg}")


def git(*args: str, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=capture, text=True)


def confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        print(f"{prompt} [auto-yes]")
        return True
    return input(f"{prompt} [y/N] ").strip().lower() in ("y", "yes")


def ensure_ignores(dry: bool) -> None:
    gi = Path(".gitignore")
    body = gi.read_text(encoding="utf-8") if gi.exists() else ""
    have = set(body.split())
    missing = [p for p in (BACKUP_IGNORE, *VENDOR_IGNORE) if p not in have]
    if not missing:
        print("   already ignored")
        return
    if dry:
        print(f"   would append {missing}")
        return
    sep = "" if not body or body.endswith("\n") else "\n"
    gi.write_text(body + sep + "\n".join(missing) + "\n", encoding="utf-8")
    print(f"   appended {missing}")


def stage_and_commit(message: str, paths: list[str], dry: bool,
                     failed: list[str]) -> None:
    def changed(p: str) -> bool:
        """Committable if present, indexed, or deleted in either tree."""
        return bool(Path(p).exists()
                    or git("ls-files", "--", p).stdout.strip()
                    or git("diff", "--cached", "--name-only", "--", p).stdout.strip()
                    or git("diff", "--name-only", "--", p).stdout.strip())

    live = [p for p in paths if changed(p)]
    if not live:
        print(f"   skip (nothing): {message}")
        return
    if dry:
        print(f"   would commit {len(live)} path(s): {message}")
        return

    # -f so ignored-but-required paths (build/.prune-backup) are included
    git("add", "-A", "-f", "--", *live, capture=False)
    if not git("diff", "--cached", "--name-only", "--", *live).stdout.strip():
        print(f"   nothing staged for: {message}")
        return
    if git("commit", "-m", message, "--", *live, capture=False).returncode:
        print(f"   COMMIT REJECTED: {message}")
        failed.append(message)
    else:
        print(f"   committed: {message}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run
    failed: list[str] = []

    say("0. preconditions")
    if git("rev-parse", "--show-toplevel").returncode:
        sys.exit("not a git repository")
    boot = Path("bootstrap.py")
    if not boot.exists() or "v33.3" not in boot.read_text(encoding="utf-8"):
        sys.exit("bootstrap.py missing or not v33.3")
    print("   repo ok, bootstrap.py is v33.3")

    plan = Path("docs/PLAN.md")
    if plan.exists():
        body = plan.read_text(encoding="utf-8", errors="replace")
        print(f"   docs/PLAN.md present ({len(body)} chars)")
        for token in ("113", "126"):
            if token not in body:
                print(f"   WARNING: PLAN.md has no §{token}")

    if not confirm("   proceed?", args.yes):
        sys.exit("aborted")

    say("1. branch")
    current = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if current == BRANCH:
        print(f"   already on {BRANCH}")
    elif dry:
        print(f"   would switch to {BRANCH}")
    else:
        exists = git("rev-parse", "--verify", "--quiet", BRANCH).returncode == 0
        a = ("checkout", BRANCH) if exists else ("checkout", "-b", BRANCH)
        if git(*a, capture=False).returncode:
            sys.exit(f"could not switch to {BRANCH}")
        print(f"   on {BRANCH}")

    say("2. remove patch scripts")
    for name in PATCHES:
        p = Path(name)
        if not p.exists():
            print(f"   {name}: absent")
        elif dry:
            print(f"   would remove {name}")
        else:
            if git("ls-files", "--error-unmatch", name).returncode == 0:
                git("rm", "-q", "--", name)
            else:
                p.unlink()
            print(f"   removed {name}")

    say("3. ignore vendored dirs and backups")
    ensure_ignores(dry)

    say("4. hook preflight")
    blocked = 0
    for cmd, label in HOOK_CHECKS:
        if dry:
            print(f"   would run {' '.join(cmd)}")
            continue
        res = subprocess.run([sys.executable, *cmd], capture_output=True, text=True)
        print(f"   {'ok  ' if res.returncode == 0 else 'FAIL'} {label}")
        if res.returncode:
            blocked += 1
            tail = (res.stdout + res.stderr).strip().splitlines()
            if tail:
                print("        " + tail[-1][:160])
    if blocked and not dry:
        print(f"\n   {blocked} hook check(s) failing — commits will be rejected.")
        if not confirm("   continue anyway?", args.yes):
            return 1

    say("5. prune commit (root deletions)")
    deleted = sorted({*git("diff", "--cached", "--name-only",
                           "--diff-filter=D").stdout.splitlines(),
                      *git("diff", "--name-only",
                           "--diff-filter=D").stdout.splitlines()})
    deleted = [p for p in deleted if p and "/" not in p]
    print(f"   {len(deleted)} root deletion(s)")
    stage_and_commit("P0: prune 35 unwired root entrypoints",
                     deleted + ["archive/", "build/"], dry, failed)

    say("6. grouped commits")
    for message, paths in GROUPS:
        stage_and_commit(message, paths, dry, failed)

    if failed:
        say("6a. commits rejected — stopping before --force")
        for m in failed:
            print(f"   {m}")
        print("   fix the hook, then: git reset && python p0_sequence.py --yes")
        return 1

    say("7. bootstrap --force")
    if dry:
        print("   would run it")
    else:
        proc = subprocess.Popen([sys.executable, "bootstrap.py", "--force"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True)
        assert proc.stdout
        for line in proc.stdout:
            print("   " + line.rstrip())
        if proc.wait():
            sys.exit("\n--force FAILED. Rollback: "
                     "git checkout bootstrap.py.v33.2.bak bootstrap.py")

    say("8. verify")
    failures = 0
    for cmd, label in [(["scripts/bootstrap-check.py"], "no tampering"),
                       (["scripts/caps_consistency.py"], "lints agree"),
                       (["scripts/audit_derive.py", "--check"], "audit round-trips")]:
        if dry:
            print(f"   would run {' '.join(cmd)}")
            continue
        res = subprocess.run([sys.executable, *cmd], capture_output=True, text=True)
        print(f"   {'ok  ' if res.returncode == 0 else 'FAIL'} {label}")
        if res.returncode:
            failures += 1
            tail = (res.stdout + res.stderr).strip().splitlines()
            if tail:
                print("        " + tail[-1][:160])

    say("9. expected reds")
    for cmd, why in EXPECTED_RED:
        if dry:
            print(f"   would run {' '.join(cmd)}")
            continue
        res = subprocess.run([sys.executable, *cmd], capture_output=True, text=True)
        print(f"   exit {res.returncode}  {' '.join(cmd)}  — {why}")

    say("10. leftovers")
    left = git("status", "--short").stdout.rstrip()
    print(left or "   clean")
    if left:
        print("   review the above, then: "
              "git add -A && git commit -m \"P0: tooling regenerated at v33.3\"")

    say("done")
    if failures:
        print(f"{failures} verification(s) failed — stop here")
        return 1
    print("Delete the .bak files once the diff reads clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())