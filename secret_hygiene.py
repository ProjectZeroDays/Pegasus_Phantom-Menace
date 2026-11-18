#!/usr/bin/env python3
"""secret_hygiene.py - scrub the leaked PoCGen credentials, add a guard, audit.

Order per the incident rule: audit -> scrub -> verify -> guard -> commit.
History rewrite is separate and gated behind --rewrite.

    python secret_hygiene.py --dry-run
    python secret_hygiene.py --yes
    python secret_hygiene.py --yes --rewrite      # destructive, makes a bundle first

Nothing is pushed unless --push.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TMP = ROOT / ".secret-hygiene-tmp"   # fresh dir; .pytest-tmp has broken ACLs/reparse points
TMP.mkdir(exist_ok=True)
README = ROOT / "weapons" / "PoCGen" / "PoCGen" / "README.md"
ENVEX = ROOT / "pegasus" / ".env.example"
GITLEAKS = ROOT / ".gitleaks.toml"
PRECOMMIT = ROOT / ".githooks" / "pre-commit"
CI = ROOT / ".github" / "workflows" / "ci.yml"
INCIDENT = ROOT / "docs" / "SECRET_INCIDENT.md"

LOG_DIR = Path(os.environ.get("PEGASUS_LOG_DIR", r"C:\Users\Project Zero\Desktop"))
if not LOG_DIR.is_dir():
    LOG_DIR = TMP
LOG = LOG_DIR / ("secret_" + time.strftime("%Y%m%d-%H%M%S") + ".txt.log")

DRY = False
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
       "GIT_INDEX_FILE": str(ROOT / ".git" / "index2")}

KEY_RE = re.compile(r"\bsk-[A-Za-z0-9]{8,}\b")
PW_RE = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9._%+-]*@C402\b")
IP_RE = re.compile(r"\b222\.20\.126\.\d{1,3}(?::\d{2,5})?")
PATTERNS = [
    ("api key", KEY_RE),
    ("password", PW_RE),
    ("base url", IP_RE),
]


def say(m): print(m, flush=True)
def ok(m): print("  [ok]   " + m, flush=True)
def skip(m): print("  [skip] " + m, flush=True)
def warn(m): print("  [warn] " + m, flush=True)


def die(m):
    print("  [FAIL] " + m, flush=True)
    say("\nlog: " + str(LOG))
    raise SystemExit(1)


def run(cmd, timeout=1800, check=False, cwd=ROOT):
    shown = " ".join(cmd) if isinstance(cmd, list) else cmd
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write("\n$ " + shown + "\n")
    if DRY and cmd[:1] != ["git"]:
        print("  [dry]  " + shown, flush=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    p = subprocess.run(cmd, cwd=cwd, env=ENV, shell=isinstance(cmd, str),
                       capture_output=True, text=True, errors="replace",
                       timeout=timeout)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(p.stdout or "")
        fh.write(p.stderr or "")
    if check and p.returncode != 0:
        die("failed (" + str(p.returncode) + "): " + shown)
    return p


# ------------------------------------------------------------------- audit

def collect(text: str) -> dict[str, str]:
    """literal -> placeholder, longest first so partials don't win."""
    found: dict[str, str] = {}
    for _, rx in PATTERNS:
        for m in rx.findall(text):
            found.setdefault(m, "")
    out = {}
    for lit in sorted(found, key=len, reverse=True):
        if KEY_RE.fullmatch(lit):
            out[lit] = "<POCGEN_DS_API_KEY>"
        elif PW_RE.fullmatch(lit):
            out[lit] = "<POCGEN_PASSWORD>"
        elif IP_RE.fullmatch(lit):
            out[lit] = "<POCGEN_BASE_URL>"
    return out


def stage_audit():
    say("\n[1/7] audit")
    targets = [
        ("working tree", ["git", "grep", "-n", "-I", "-E",
                          "@C402|sk-[A-Za-z0-9]{8,}|222\\.20\\.126\\.", "--", "."]),
        ("HEAD", ["git", "grep", "-n", "-I", "-E",
                  "@C402|sk-[A-Za-z0-9]{8,}|222\\.20\\.126\\.", "HEAD", "--", "."]),
        ("all refs", ["git", "grep", "-n", "-I", "-E",
                      "@C402|sk-[A-Za-z0-9]{8,}|222\\.20\\.126\\.",
                      "$(git rev-list --all)", "--", "."]),
    ]
    hits = {}
    for label, cmd in targets:
        p = run(cmd if not isinstance(cmd, list) else cmd)
        lines = [ln for ln in (p.stdout or "").splitlines() if ln.strip()]
        hits[label] = lines
        say(f"  {label}: {len(lines)} line(s)")
        for ln in lines[:12]:
            say("    " + ln[:160])
        if len(lines) > 12:
            say(f"    ... {len(lines) - 12} more")

    untracked = run(["git", "ls-files", "--others", "--exclude-standard"]).stdout or ""
    scan = 0
    for rel in untracked.splitlines():
        p = ROOT / rel.strip()
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if KEY_RE.search(text) or PW_RE.search(text):
            warn("untracked file carries a secret: " + rel)
            scan += 1
    if not scan:
        ok("no untracked file carries one")

    src = README.read_text(encoding="utf-8") if README.exists() else ""
    lit = collect(src)
    say(f"  README literals to scrub: {len(lit)}")
    for k, v in lit.items():
        say(f"    {k[:46]:<48} -> {v}")
    (TMP / "replacements.txt").write_text(
        "".join(f"{k}==>{v}\n" for k, v in lit.items()), encoding="utf-8", newline="\n")
    return lit


# ------------------------------------------------------------------- scrub

PS_FIX = [
    (re.compile(r"^\s*export\s+([A-Z0-9_]+)=(.*)$", re.M), r'$env:\1="\2"'),
    (re.compile(r"^\s*set\s+([A-Z0-9_]+)=(.*)$", re.M), r'$env:\1="\2"'),
]


def stage_scrub(lit: dict[str, str]):
    say("\n[2/7] scrub the README")
    if not README.exists():
        warn("README not found")
        return
    text = README.read_text(encoding="utf-8")
    before = text
    for k, v in lit.items():
        text = text.replace(k, v)
    changed = sum(1 for a, b in zip(before.splitlines(), text.splitlines()) if a != b)
    if changed:
        ok(f"{changed} line(s) de-secreted")
    else:
        skip("no literal found")

    ps = 0
    for rx, repl in PS_FIX:
        text, n = rx.subn(repl, text)
        ps += n
    if ps:
        ok(f"{ps} PowerShell line(s) converted to $env: form")

    if text != before and not DRY:
        README.write_text(text, encoding="utf-8", newline="\n")

    print("\n  --- changed lines ---")
    for a, b in zip(before.splitlines(), text.splitlines()):
        if a != b:
            print("  - " + a.strip()[:130])
            print("  + " + b.strip()[:130])


def stage_envex():
    say("\n[3/7] .env.example weak values")
    if not ENVEX.exists():
        skip("absent")
        return
    text = ENVEX.read_text(encoding="utf-8")
    before = text
    text = re.sub(r"(?m)^(\s*PEGASUS__METASPLOIT__RPC_PASSWORD\s*=\s*)msf123\s*$",
                  r"\1<rpc-password>", text)
    text = text.replace("msf123", "<rpc-password>")
    text = text.replace("change-me-in-production", "<change-me>")
    if text != before:
        if not DRY:
            ENVEX.write_text(text, encoding="utf-8", newline="\n")
        ok("placeholders substituted")
    else:
        skip("already placeholder")


# ------------------------------------------------------------------- verify

def stage_verify():
    say("\n[4/7] verify")
    p = run(["git", "grep", "-n", "-I", "-E",
             "@C402|sk-[A-Za-z0-9]{8,}|222\\.20\\.126\\.", "--", "."])
    left = [ln for ln in (p.stdout or "").splitlines() if ln.strip()]
    if left:
        warn(f"{len(left)} hit(s) remain in the working tree")
        for ln in left[:10]:
            say("    " + ln[:150])
        if any("README" not in ln for ln in left):
            warn("some are outside the README - inspect before committing")
    else:
        ok("working tree clean")

    gl = run(["gitleaks", "version"])
    if gl.returncode != 0:
        warn("gitleaks not installed - install to use the guard")
        return
    ok("gitleaks " + (gl.stdout or "").strip())
    p = run(["gitleaks", "detect", "--no-git", "--redact", "--verbose"], timeout=900)
    if p.returncode == 0:
        ok("gitleaks: no leaks in the working tree")
    else:
        warn("gitleaks flagged something - read the log")


# ------------------------------------------------------------------- guard

GITLEAKS_CFG = """# Pegasus secret scanning.
# The PoCGen README leaked provider keys in pushed history; these rules exist so
# the next one is caught before commit.

title = "pegasus"

[extend]
useDefault = true

[[rules]]
id = "pocgen-provider-key"
description = "PoCGen provider API key"
regex = '''\\bsk-[A-Za-z0-9]{8,}\\b'''
tags = ["key", "pocgen"]

[[rules]]
id = "pocgen-password"
description = "PoCGen credential with the @C402 suffix"
regex = '''\\b[A-Za-z0-9][A-Za-z0-9._%+-]*@C402\\b'''
tags = ["password", "pocgen"]

[[rules]]
id = "pocgen-base-url"
description = "PoCGen hardcoded base URL"
regex = '''\\b222\\.20\\.126\\.\\d{1,3}(?::\\d{2,5})?'''
tags = ["url", "pocgen"]

[allowlist]
description = "documented placeholders and vendored lockfiles"
paths = [
  '''(^|/)package-lock\\.json$''',
  '''(^|/)uv\\.lock$''',
  '''\\.example$''',
]
regexes = [
  '''<POCGEN_[A-Z_]+>''',
]
"""

PRECOMMIT_BLOCK = """
# --- secret scan (gitleaks) -------------------------------------------------
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-git --redact --quiet --staged || {
    echo "commit blocked: gitleaks found a secret in the staged tree" >&2
    echo "scrub it, or add an allowlist entry to .gitleaks.toml" >&2
    exit 1
  }
else
  echo "note: gitleaks not installed, secret scan skipped" >&2
fi
"""


def stage_guard():
    say("\n[5/7] guard")
    if GITLEAKS.exists():
        skip(".gitleaks.toml present")
    else:
        if not DRY:
            GITLEAKS.write_text(GITLEAKS_CFG, encoding="utf-8", newline="\n")
        ok(".gitleaks.toml written")

    if not PRECOMMIT.exists():
        warn("no pre-commit hook")
    else:
        text = PRECOMMIT.read_text(encoding="utf-8")
        if "gitleaks" in text:
            skip("pre-commit already scans")
        else:
            if not DRY:
                PRECOMMIT.write_text(text.rstrip("\n") + "\n" + PRECOMMIT_BLOCK,
                                     encoding="utf-8", newline="\n")
            ok("gitleaks added to pre-commit")

    if CI.exists():
        text = CI.read_text(encoding="utf-8")
        if "gitleaks" in text:
            skip("CI already scans")
        else:
            job = (
                "\n  secret-scan:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "        with: { fetch-depth: 0 }\n"
                "      - uses: gitleaks/gitleaks-action@v2\n"
                "        env:\n"
                "          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"
            )
            if not DRY:
                CI.write_text(text.rstrip("\n") + "\n" + job, encoding="utf-8", newline="\n")
            ok("secret-scan job added to CI")
    else:
        warn("ci.yml absent")


# ----------------------------------------------------------------- incident

INCIDENT_DOC = """# Secret incident: PoCGen provider credentials

**Status:** rotation pending (operator), scrub in progress
**Found in:** `weapons/PoCGen/PoCGen/README.md`, present in pushed history from
`22d4d0a2` onward.

## Order of operations

Rotation is the fix. Scrub and history rewrite are cosmetic by comparison — the
literal is in every clone and every fork that already fetched.

### 1. Rotate, at the provider

- [ ] DeepSeek API key (`sk-…`) — revoke, issue new
- [ ] Qwen / DashScope API key — revoke, issue new
- [ ] Any other `POCGEN_*_API_KEY` value in the README — revoke, issue new
- [ ] Every password carrying the `@C402` suffix — change at the provider
- [ ] Confirm each old value fails authentication after rotation

### 2. Scrub the tree

`python secret_hygiene.py --yes` replaces the literals in the README with
`<POCGEN_DS_API_KEY>`, `<POCGEN_PASSWORD>` and `<POCGEN_BASE_URL>`, and fixes the
PowerShell example lines to the `$env:NAME="value"` form.

### 3. Rewrite history (only with team agreement)

`python secret_hygiene.py --yes --rewrite`

- bundles `main` to `.pytest-tmp/backup-<stamp>.bundle` first
- `git filter-repo --replace-text .pytest-tmp/replacements.txt`
- force-push with `--force-with-lease`

Consequences: every clone must re-clone or `reset --hard`; open PRs need rebasing;
the tag SHAs change. Do not do this while a release is mid-flight.

### 4. Verify

`python secret_hygiene.py --yes --only verify` must report a clean working tree
and a clean gitleaks run. Also check the GitHub code search UI once, since it has
its own index.

### 5. Prevent

`.gitleaks.toml` plus the pre-commit hook plus the CI `secret-scan` job. The
hook is `--staged` so it only scans what is being committed.

## What this does not cover

Rotation of anything not in this README, and the `ghp_` PAT which is a separate
incident already recorded in `docs/PLAN.md`.
"""


def stage_incident():
    say("\n[6/7] incident record")
    if INCIDENT.exists():
        skip("present")
        return
    if not DRY:
        INCIDENT.parent.mkdir(parents=True, exist_ok=True)
        INCIDENT.write_text(INCIDENT_DOC, encoding="utf-8", newline="\n")
    ok("docs/SECRET_INCIDENT.md written with the rotation checklist")


# ------------------------------------------------------------------ commit

def stage_commit():
    say("\n[7/7] commit")
    for rel in ("weapons/PoCGen/PoCGen/README.md", "pegasus/.env.example",
                ".gitleaks.toml", ".githooks/pre-commit",
                ".github/workflows/ci.yml", "docs/SECRET_INCIDENT.md"):
        if (ROOT / rel).exists():
            run(["git", "add", "--", rel])
    print((run(["git", "status", "--porcelain"]).stdout or "").rstrip()[:2000])
    if DRY:
        return
    body = (
        "PoCGen README carried live provider keys and @C402 passwords in pushed\n"
        "history. Rotation is the real fix; this scrubs the literals, adds a\n"
        "gitleaks guard at pre-commit and in CI, and records the incident with the\n"
        "rotation checklist.\n\n"
        "History rewrite is separate and not done here - see docs/SECRET_INCIDENT.md.\n"
    )
    for prefix in ("P16:", "P9:", "PLAN:"):
        p = run(["git", "commit", "-m",
                 prefix + " scrub PoCGen credentials, add a secret guard\n\n" + body])
        if p.returncode == 0:
            ok("committed with " + repr(prefix))
            return
        warn(((p.stderr or p.stdout).strip().splitlines() or ["failed"])[-1])
    die("commit rejected")


# ----------------------------------------------------------------- rewrite

def stage_rewrite():
    say("\n[rewrite] history - destructive")
    bundle = TMP / ("backup-" + time.strftime("%Y%m%d-%H%M%S") + ".bundle")
    run(["git", "bundle", "create", str(bundle), "--all"], check=True)
    ok("backup " + bundle.name + "  " + str(bundle.stat().st_size) + " B")

    if run(["git", "filter-repo", "--version"]).returncode != 0:
        warn("git-filter-repo not installed:  python -m pip install git-filter-repo")
        warn("backup is made; re-run --rewrite once installed")
        return

    repl = TMP / "replacements.txt"
    if not repl.exists() or not repl.read_text(encoding="utf-8").strip():
        die("no replacements - run without --rewrite first")
    run(["git", "filter-repo", "--replace-text", str(repl), "--force"], check=True)
    ok("history rewritten")

    if "--push" in sys.argv:
        run(["git", "remote", "add", "origin",
             "https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace.git"])
        p = run(["git", "push", "--force-with-lease", "origin", "--all"], timeout=1800)
        if p.returncode != 0:
            die("force-push failed:\n" + (p.stderr or p.stdout)[-600:])
        ok("force-pushed")
    else:
        warn("not pushed - re-run with --push to force-push")


STAGES = [("audit", stage_audit), ("scrub", None), ("envex", stage_envex),
          ("verify", stage_verify), ("guard", stage_guard),
          ("incident", stage_incident), ("commit", stage_commit)]
NAMES = [n for n, _ in STAGES] + ["rewrite"]


def main():
    global DRY
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--rewrite", action="store_true")
    ap.add_argument("--only", nargs="*", default=[], choices=NAMES)
    ap.add_argument("--skip", nargs="*", default=[], choices=NAMES)
    a = ap.parse_args()
    DRY = a.dry_run
    say("log: " + str(LOG))
    if not DRY and not a.yes:
        if input("proceed? [y/N] ").strip().lower() not in ("y", "yes"):
            return 1

    lit = {}
    for name, fn in STAGES:
        if a.only and name not in a.only:
            continue
        if name in a.skip:
            skip(name)
            continue
        if name == "audit":
            lit = stage_audit()
        elif name == "scrub":
            stage_scrub(lit)
        else:
            fn()

    if a.rewrite and (not a.only or "rewrite" in a.only):
        stage_rewrite()
    say("\nlog: " + str(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())