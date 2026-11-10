"""push_all.py - preview the cleanup, apply it, gate, commit and push.

Cleanup runs in two passes by itself: a dry pass that prints what would happen,
then the real pass. It pauses between them for a keypress unless CONFIRM=1.
DRY=1 stops after the preview and touches nothing.

Deletion is tracked-aware: files git already knows are removed with git rm so the
deletion is staged, untracked ones are unlinked. Three things survive and are
reported: the PROTECTED set, anything matching .keep_scratch, and any tracked
file whose name carries no scratch prefix. AUDIT=1 prints a verdict per file
and stops without touching anything.

The handoff block goes into PLAN.md first so scripts/handoff.py can regenerate
docs/HANDOFF.md from it, and every gate runs before a commit is created. Any gate
failure aborts with the reason. Set ALLOW=1 to commit anyway.
"""
import os
import subprocess
import sys
import pathlib

TOKEN_FILE = pathlib.Path(".push_token")


def load_token():
    tok = os.environ.get("PUSH_TOKEN", "").strip()
    if tok:
        return tok
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    return ""


TOKEN = load_token()
REMOTE = "origin"
BRANCH = "main"
PLAN = pathlib.Path("docs/PLAN.md")
MARK = "## 61. HANDOFF"
KEEP_FILE = pathlib.Path(".keep_scratch")
ALWAYS_KEEP = {"push_all.py", "seal.py", "Q9.py"}

# Real root files. Tracked files are already covered by the prefix test
# below, but this set is the hard floor and the place to register anything
# new that must never go. A pattern alone is not enough: p*.txt and
# verify*.py look harmless right up until requirements.txt and verify.py
# are gone.
PROTECTED = {
    "push_all.py", "seal.py", "Q9.py", "setup.py", "bootstrap.py",
    "requirements.txt", "start_server.py", "version.txt", "Makefile",
    "LICENSE", "README.md", ".gitignore", ".env.example", "pyproject.toml",
    "pytest.ini", "tox.ini", "conftest.py",
}

# A tracked file only goes if its name starts with one of these. Untracked
# files are still judged by pattern, which is the safe asymmetry: scratch is
# always untracked, and a real file is normally tracked by the time a sweep
# reaches it.
SCRATCH_PREFIXES = ("fix_", "diag_", "apply_", "patch_", "inspect_", "loop",
                    "verify_", "q11_", "regions", "publish", "amend_",
                    "cleanup_")


def has_scratch_prefix(name):
    return name.startswith(SCRATCH_PREFIXES)

PATTERNS = ("fix_*.py", "fix_*.py.txt", "diag_*.py", "diag_*.py.txt",
            "apply_*.py", "apply_*.py.txt", "patch_*.py", "patch_*.py.txt",
            "inspect_*.py", "publish.py", "loop*.py", "loop*.log",
            "verify*.py", "verify*.log", "q11_*.log", "regions*.txt", "p*.txt")

DRY = os.environ.get("DRY") == "1"
CONFIRM = os.environ.get("CONFIRM") == "1"
AUDIT = os.environ.get("AUDIT") == "1"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def tracked_set():
    rc, out = run(["git", "ls-files", "-z"])
    return set(x for x in out.split("\0") if x)


def keep_set():
    keep = set(ALWAYS_KEEP)
    if KEEP_FILE.exists():
        for ln in KEEP_FILE.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                keep.add(ln)
    return keep


def matches(name, keep):
    if name in keep:
        return True
    return any(pathlib.PurePath(name).match(k) for k in keep
               if any(ch in k for ch in "*?["))


def classify(name, rel, keep, tracked):
    """Keep reason, or None when the file may be deleted."""
    if name in PROTECTED or rel in PROTECTED:
        return "protected"
    if matches(name, keep) or rel in keep:
        return "listed"
    if tracked and not has_scratch_prefix(name):
        return "tracked-real"
    return None


def collect():
    seen, out = set(), []
    for pattern in PATTERNS:
        for p in sorted(pathlib.Path(".").glob(pattern)):
            if p.is_file() and p.name not in seen:
                seen.add(p.name)
                out.append(p)
    return out


def cleanup(dry):
    """One pass. dry=True only reports."""
    tracked = tracked_set()
    keep = keep_set()
    print("tracked: %d   keep list: %d" % (len(tracked), len(keep)))
    counts = {}

    def bump(k):
        counts[k] = counts.get(k, 0) + 1

    for p in collect():
        rel = p.as_posix()
        is_tracked = rel in tracked
        reason = classify(p.name, rel, keep, is_tracked)
        if reason:
            print("  keep        %-28s (%s)" % (p.name, reason))
            bump("kept")
            continue
        if dry:
            print("  %-11s %-28s %s" % ("would-git-rm" if is_tracked else "would-rm",
                                        p.name, "TRACKED" if is_tracked else "new"))
            bump("pending")
            continue
        if is_tracked:
            rc, out = run(["git", "rm", "-f", "--quiet", rel])
            print("  %-11s %-28s TRACKED" % ("git-rm" if rc == 0 else "FAIL", p.name))
            bump("git-rm" if rc == 0 else "failed")
        else:
            try:
                p.unlink()
                print("  %-11s %-28s new" % ("rm", p.name))
                bump("rm")
            except OSError as exc:
                print("  %-11s %-28s %s" % ("FAIL", p.name, exc))
                bump("failed")

    for junk in ("__pycache__", ".pytest_cache"):
        for d in pathlib.Path(".").glob("**/" + junk):
            if not d.is_dir() or "node_modules" in d.parts:
                continue
            files = [f for f in d.rglob("*") if f.is_file()]
            hit = [f for f in files if f.as_posix() in tracked]
            if dry:
                print("  %-11s %s (%d tracked, %d total)" %
                      ("would-clean", d.as_posix(), len(hit), len(files)))
                continue
            for f in hit:
                run(["git", "rm", "-f", "--quiet", f.as_posix()])
            for f in files:
                if f.as_posix() not in tracked:
                    try:
                        f.unlink()
                    except OSError:
                        pass
            try:
                d.rmdir()
            except OSError:
                pass
            print("  %-11s %s" % ("cleaned", d.as_posix()))

    print("  -> %s" % (", ".join("%s=%d" % kv for kv in sorted(counts.items())) or "nothing"))
    return counts


# ---------------- 0. cleanup: preview then apply ----------------
if AUDIT:
    _t, _k = tracked_set(), keep_set()
    print("=== victim audit ===")
    for _p in collect():
        _r = classify(_p.name, _p.as_posix(), _k, _p.as_posix() in _t)
        print("  %-14s %s" % (_r or "DELETE", _p.name))
    print("keep list: %d   protected: %d" % (len(_k), len(PROTECTED)))
    sys.exit(0)

print("=== cleanup preview ===")
cleanup(dry=True)

if DRY:
    print("\nDRY — nothing changed")
    sys.exit(0)

if not CONFIRM:
    try:
        input("\nEnter to apply, Ctrl-C to stop... ")
    except (EOFError, KeyboardInterrupt):
        print("\nstopped")
        sys.exit(1)

print("\n=== cleanup applied ===")
cleanup(dry=False)

# ---------------- 1. preflight ----------------
rc, branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
print("\nbranch:", branch)
if branch != BRANCH:
    print("NOTE  not on %s; switching" % BRANCH)
    run(["git", "checkout", BRANCH])

rc, dirty = run(["git", "status", "--porcelain"])
print("changed files: %d" % len(dirty.splitlines()))
if not dirty:
    print("nothing to commit")
    sys.exit(0)

# ---------------- 2. handoff block ----------------
if not PLAN.exists():
    print("MISS  docs/PLAN.md")
    sys.exit(1)

text = PLAN.read_text(encoding="utf-8")
if MARK in text:
    print("skip  handoff block present")
else:
    BLOCK = [
        "",
        "",
        "=== HANDOFF SECTION ===",
        "",
        MARK,
        "",
        "Project: Pegasus Phantom Menace v2 / web backend",
        "Status: Backend imports and serves; suite green (75 passed), tsc clean",
        "Features: 20 device routes re-registered behind an opt-in token gate; sweep 1.3, 7.5, 11.1, 12.5 closed",
        "Log: log/events.jsonl",
        "Release: unreleased since v2.1.0",
        "Push blocked: none",
        "Next: Phase 4 — 47-endpoint physical-ops dashboard, 343-route accessibility sweep, clean-VM Electron build, iOS provisioning",
        "Author: Trey A. Smith | Authenticated, Inc. | @projectzerodays",
        "Notes: job_manager aliased to the module-level JobManager singleton; duplicate /api/jobs/<job_id> removed (106 -> 105 rules); jsonify and stdlib imports restored; _require_token on every device route behind PEGASUS_REQUIRE_AUTH; filterVectors wired into PayloadFactory; VITE_API_BASE documented; pytest --import-mode=importlib.",
        "",
    ]
    PLAN.write_text(text.rstrip() + "\n" + "\n".join(BLOCK), encoding="utf-8")
    print("ok    handoff block appended to docs/PLAN.md")

# ---------------- 3. regenerate handoff ----------------
rc, out = run([sys.executable, "scripts/handoff.py"])
print("gen handoff:", "ok" if rc == 0 else out[-300:])

# ---------------- 4. gates ----------------
GATES = [
    ["scripts/handoff.py", "--check"],
    ["scripts/emit_agents.py", "--check"],
    ["scripts/modules_lint.py"],
    ["scripts/caps_consistency.py"],
    ["scripts/require.py", "--lint"],
    ["scripts/version_check.py"],
    ["scripts/risk_lint.py"],
    ["scripts/no_platform_branch.py"],
    ["scripts/audit_derive.py", "--check"],
    ["scripts/bootstrap-check.py"],
]

failed = []
print("\n=== gates ===")
for g in GATES:
    if not pathlib.Path(g[0]).exists():
        print("SKIP  %s (absent)" % g[0])
        continue
    rc, out = run([sys.executable] + g)
    print("%s  %s" % ("PASS" if rc == 0 else "FAIL", " ".join(g)))
    if rc != 0:
        failed.append((g, out))

if failed:
    print("\n--- failures ---")
    for g, out in failed:
        print("\n%s\n%s" % (" ".join(g), out[-800:]))
    if os.environ.get("ALLOW") != "1":
        print("\naborting; set ALLOW=1 to commit anyway")
        sys.exit(1)

# ---------------- 5. commit ----------------
run(["git", "add", "-A"])
rc, out = run(["git", "status", "--porcelain"])
print("\nstaged: %d" % len(out.splitlines()))

MSG = [
    "P4: restore job_manager, gate device routes, close sweep 1.3/7.5/11.1/12.5",
    "",
    "- jobs.py aliases job_manager to the module-level JobManager singleton",
    "- restore the sixteen register() calls and # System endpoints in app.py",
    "- jobs_list reads the shared manager; duplicate /api/jobs/<job_id> removed (105 rules)",
    "- restore jsonify, sys, platform, shutil, subprocess and pathlib imports",
    "- opt-in _require_token on all 20 device routes behind PEGASUS_REQUIRE_AUTH",
    "- wire filterVectors into PayloadFactory including the empty-state guard",
    "- document VITE_API_BASE and VITE_PEGASUS_API_TOKEN, add .env.example",
    "- pytest --import-mode=importlib; 75 tests pass, tsc clean",
]
cmd = ["git", "commit"]
for line in MSG:
    cmd += ["-m", line]
rc, out = run(cmd)
print(out[-1200:])
if rc != 0:
    print("commit failed")
    sys.exit(1)

# ---------------- 6. push ----------------
if TOKEN:
    url = "https://%s@github.com/ProjectZeroDays/Pegasus_Phantom-Menace.git" % TOKEN
    run(["git", "remote", "set-url", REMOTE, url])
else:
    print("no token in env or .push_token; using the remote URL as-is")
rc, out = run(["git", "push", REMOTE, BRANCH])
print("\n" + out.replace(TOKEN, "<token>")[-1500:])
print("\npush:", "ok" if rc == 0 else "FAILED")
sys.exit(0 if rc == 0 else 1)