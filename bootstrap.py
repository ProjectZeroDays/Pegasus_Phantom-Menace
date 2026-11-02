#!/usr/bin/env python3
"""Pegasus bootstrap v33.3 — cross-platform, checksum-guarded, backup-first.

Writes tooling, hooks, skills, adapters, contracts and the capability scaffold;
consolidates the version; reconciles the Makefile; prunes or regenerates unwired
root files; wires hooksPath; provisions pyyaml; runs the sequence and verifies it.

v33.3 removes the possibility of the two cap lints disagreeing quietly:
  * scripts/capreg.py is the single AST-based parser; both lints import it
  * modules_lint now fails on an orphan cap, the same condition caps_matrix fails on
  * modules_lint sweeps the whole enum, so an unreferenced orphan is caught too
  * modules_lint also fails on a phantom `provides` entry (a typo in the registry)
  * caps-consistency asserts the two lints return the same verdict, and is a gate
  * build/caps_orphans.allow waives an orphan deliberately, with a reason
  * build/caps_baseline.json records provider counts; an edge drop is reported
  * the matrix is emitted as JSON as well as markdown, so CI need not scrape prose

Self-check before touching anything (64 assertions, 16 of them negative):
    python bootstrap.py --self-test

Usage:
    python bootstrap.py               # normal
    python bootstrap.py --force       # overwrite locally modified tooling
    python bootstrap.py --no-prune    # leave root files in place
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STATE = Path(".bootstrap-state")
TOOLING = [
    "scripts/handoff.py", "scripts/require.py", "scripts/emit_agents.py",
    "scripts/bootstrap-check.py", "scripts/verify.py", "scripts/openapi_snapshot.py",
    "scripts/module_new.py", "scripts/parity.py", "scripts/version_check.py",
    "scripts/modules_lint.py", "scripts/audit_derive.py", "scripts/caps_matrix.py",
    "scripts/risk_lint.py", "scripts/no_platform_branch.py", "scripts/capability_check.py",
    "scripts/capreg.py", "scripts/caps_consistency.py",
    "pegasus/tests/contract/test_agents.py",
    ".githooks/pre-commit", ".githooks/pre-push", ".githooks/commit-msg",
]
GATES = {f"G{i}" for i in range(1, 25)}

MANAGED_BEGIN = "# >>> pegasus bootstrap managed targets (regenerated) >>>"
MANAGED_END = "# <<< pegasus bootstrap managed targets <<<"

PYRESOURCES = ("version.txt", "version-web.txt")
RESOURCE_DEST = Path("packaging/pyinstaller")
VERSION_FILE = Path("pegasus/VERSION")
SEMVER = re.compile(r"(?:filevers|prodvers)\s*=\s*\(\s*(\d+),\s*(\d+),\s*(\d+)")
STRVER = re.compile(r"StringStruct\('(?:FileVersion|ProductVersion)',\s*'([0-9][0-9.]*)'\)")
TRIPLE = re.compile(r"^\d+\.\d+\.\d+$")

PRUNE: list[tuple[str, str, str]] = [
    ("oracle.py", "DELETE", "dist leg is print('PASS'); superseded by pcap_engine"),
    ("phase_engine.py", "DELETE", "can_enter compares a serial to the literal '*'"),
    ("blast_radius_estimator.py", "DELETE", "superseded by harness blast classes"),
    ("snapshot_before_mutate.py", "DELETE", "superseded by harness quarantine"),
    ("shadow_deploy.py", "DELETE", "superseded by harness dry-run"),
    ("idempotent_wrapper.py", "DELETE", "superseded by control/undo"),
    ("promotion.py", "DELETE", "no caller; superseded by gate G13"),
    ("mutation.py", "DELETE", "superseded by harness mutators"),
    ("self_healing.py", "DELETE", "no caller; superseded by control/rollback"),
    ("observability_trace.py", "DELETE", "superseded by audit log"),
    ("test_all.py", "DELETE", "superseded by pegasus/tests tiers"),
    ("smoke_manual.py", "DELETE", "superseded by make preflight"),
    ("count_repos.py", "DELETE", "one-shot; superseded by make map"),
    ("find_repos.py", "DELETE", "one-shot; superseded by make map"),
    ("feature_inventory.py", "DELETE", "one-shot; superseded by make parity"),
    ("build_final.log", "DELETE", "build transcript; read by no target"),
    (".openfable-skills", "REGENERATE", "re-emitted as a generated adapter"),
    (".zfable-skills", "REGENERATE", "re-emitted as a generated adapter"),
    ("pegasus_web.py", "ARCHIVE", "moves to pegasus/ui/api/app.py in P3b"),
    ("verify_blob.py", "ARCHIVE", "merges into scripts/verify.py in P3c"),
    ("verify_integration.py", "ARCHIVE", "merges into scripts/verify.py in P3c"),
    ("setup_init.py", "ARCHIVE", "merges into pegasus/core in P5"),
    ("setup_wizard_first_run.py", "ARCHIVE", "merges into pegasus/core in P5"),
    ("knowledge_db.py", "ARCHIVE", "merges into pegasus/modules/memory in P4"),
    ("target_manifest.schema.json", "ARCHIVE", "moves to pegasus/modules/journal in P4"),
    ("create_release.sh", "ARCHIVE", "moves to scripts/ in P7"),
    ("release_v3_notes.md", "ARCHIVE", "moves to docs/releases/ in P8"),
    ("release_v3_1_notes.md", "ARCHIVE", "moves to docs/releases/ in P8"),
    ("README_BUNDLE.md", "ARCHIVE", "merges into README.md in P8"),
    ("Pegasus-Web.spec", "ARCHIVE", "moves to packaging/pyinstaller/web.spec in P7"),
    ("fix_inits.py", "MOVE", "belongs in scripts/"),
    ("benchmark_multi.py", "MOVE", "belongs in scripts/"),
    ("cloud_deploy.py", "MOVE", "belongs in scripts/"),
    ("pegasus.icns", "MOVE", "belongs in assets/icons/"),
    ("pegasus.ico", "MOVE", "belongs in assets/icons/"),
]
MOVE_DEST = {
    "fix_inits.py": "scripts/fix_inits.py",
    "benchmark_multi.py": "scripts/benchmark_multi.py",
    "cloud_deploy.py": "scripts/cloud_deploy.py",
    "pegasus.icns": "assets/icons/pegasus.icns",
    "pegasus.ico": "assets/icons/pegasus.ico",
}


def say(msg: str) -> None:
    print(f"\033[1;36m{msg}\033[0m" if os.name != "nt" else msg)


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def have(exe: str) -> bool:
    return shutil.which(exe) is not None


def is_admin() -> bool:
    if os.name == "nt":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def privileged(cmd: list[str]) -> list[str]:
    if is_admin() or os.name == "nt":
        return cmd
    if have("sudo"):
        return ["sudo"] + cmd
    return cmd


def run(cmd: list[str], check: bool = False) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    out = (proc.stdout or "") + (proc.stderr or "")
    if check and proc.returncode != 0:
        die(f"{' '.join(cmd)} failed:\n{out}")
    return proc.returncode, out


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(rel: str, body: str, executable: bool = False) -> None:
    path = Path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")
    if executable:
        try:
            os.chmod(path, 0o755)
        except OSError:
            pass


def stamp() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip() or "noh"


def tracked(rel: str) -> bool:
    return run(["git", "ls-files", "--error-unmatch", "--", rel])[0] == 0


def git_remove(rel: str) -> None:
    if tracked(rel):
        run(["git", "rm", "-r", "-q", "-f", "--ignore-unmatch", "--", rel])


# --------------------------------------------------------------------- pyyaml
def pyyaml_available() -> bool:
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


def pyyaml_install() -> bool:
    system = platform.system()
    attempts: list[tuple[str, list[str]]] = [
        ("pip --user", [sys.executable, "-m", "pip", "install", "--user", "pyyaml"]),
        ("pip --user --break-system-packages",
         [sys.executable, "-m", "pip", "install", "--user",
          "--break-system-packages", "pyyaml"]),
    ]
    if system == "Darwin":
        if have("brew"):
            attempts.append(("brew", ["brew", "install", "pyyaml"]))
    elif system == "Linux":
        if have("apt-get"):
            attempts.append(("apt-get", privileged(["apt-get", "install", "-y", "python3-yaml"])))
        if have("dnf"):
            attempts.append(("dnf", privileged(["dnf", "install", "-y", "python3-pyyaml"])))
        if have("zypper"):
            attempts.append(("zypper", privileged(["zypper", "install", "-y", "python3-PyYAML"])))
        if have("pacman"):
            attempts.append(("pacman", privileged(["pacman", "-S", "--noconfirm", "python-yaml"])))
        if have("apk"):
            attempts.append(("apk", privileged(["apk", "add", "py3-yaml"])))
    elif system == "Windows":
        if have("py"):
            attempts.append(("py -m pip", ["py", "-m", "pip", "install", "--user", "pyyaml"]))
        if have("winget"):
            attempts.append(("winget", ["winget", "install", "--id",
                                        "Python.Python.3.12", "-e", "--silent"]))
    for label, cmd in attempts:
        say(f"    trying {label}")
        code, out = run(cmd)
        if pyyaml_available():
            say(f"    pyyaml installed via {label}")
            return True
        if code != 0 and "already satisfied" not in out.lower():
            print(f"      {label} failed: {out.strip().splitlines()[-1:] or ''}")
    return pyyaml_available()


def ensure_pyyaml() -> None:
    say("0a/21 checking pyyaml")
    if pyyaml_available():
        say("    present")
        return
    say(f"    missing — provisioning for {platform.system()}")
    if not pyyaml_install():
        die(
            "could not install pyyaml automatically.\n"
            "  Debian/Ubuntu: sudo apt-get install -y python3-yaml\n"
            "  Fedora:        sudo dnf install -y python3-pyyaml\n"
            "  Arch:          sudo pacman -S python-yaml\n"
            "  Alpine:        sudo apk add py3-yaml\n"
            "  macOS:         brew install pyyaml\n"
            "  Windows:       py -m pip install --user pyyaml\n"
            "  anywhere:      python -m pip install --user pyyaml"
        )


# ------------------------------------------------------------------- payloads
CAPREG_PY = '''#!/usr/bin/env python3
"""Single source of truth for the cap enum and the transport provider map.

Both modules_lint and caps_matrix import this. Neither parses core/caps.py
itself, so they cannot disagree about what a cap is — the shared module is the
agreement, not a convention.

AST, not regex: a docstring edit, a reformat, or a second enum cannot silently
change the parsed set. Parsing also proves the file is valid Python.

Exit conventions the lints share: 0 clean, 2 violation, 3 precondition.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

CAPS = Path("core/caps.py")
REGISTRY = Path("transports/registry.yaml")
ALLOW = Path("build/caps_orphans.allow")
BASELINE = Path("build/caps_baseline.json")
ENUM = "Cap"


class Precondition(Exception):
    """The tree is not shaped as expected; exit 3, not 2."""


def cap_values(caps: Path = CAPS) -> list[str]:
    """Every Cap member value, in declaration order."""
    if not caps.exists():
        raise Precondition(f"{caps} missing")
    tree = ast.parse(caps.read_text(encoding="utf-8"), filename=str(caps))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == ENUM:
            out = []
            for stmt in node.body:
                if (isinstance(stmt, ast.Assign)
                        and isinstance(stmt.value, ast.Constant)
                        and isinstance(stmt.value.value, str)):
                    out.append(stmt.value.value)
            if not out:
                raise Precondition(f"{ENUM} in {caps} has no string members")
            return out
    raise Precondition(f"no class {ENUM} in {caps}")


def providers(registry: Path = REGISTRY) -> dict[str, list[str]]:
    """cap value -> transport names advertising it."""
    if not registry.exists():
        raise Precondition(f"{registry} missing")
    import yaml
    rows = yaml.safe_load(registry.read_text(encoding="utf-8")) or []
    if not isinstance(rows, list) or not rows:
        raise Precondition(f"{registry} has no transports")
    out: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise Precondition(f"{registry} has a non-mapping row")
        name = row.get("name", "?")
        for cap in row.get("provides") or []:
            out.setdefault(cap, []).append(name)
    return out


def allowlist(path: Path = ALLOW) -> dict[str, str]:
    """cap value -> reason. Blank lines and # comments ignored."""
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        head, _, tail = line.partition("#")
        cap = head.strip()
        if cap:
            out[cap] = tail.strip()
    return out


def split_orphans(values, provided, allowed):
    """(blocking, waived). Waiving an absent cap is itself reported."""
    orphans = [c for c in values if c not in provided]
    waived = [c for c in orphans if c in allowed]
    blocking = [c for c in orphans if c not in allowed]
    stale = sorted(c for c in allowed if c not in orphans)
    return blocking, waived, stale


def phantom_provides(values, provided) -> list[str]:
    """Caps a transport advertises but the enum does not define — a typo."""
    known = set(values)
    return sorted(c for c in provided if c not in known)


def load_baseline(path: Path = BASELINE) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_baseline(provided, path: Path = BASELINE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({k: len(v) for k, v in sorted(provided.items())}, indent=2) + "\\n",
        encoding="utf-8")


def dropped_edges(baseline, provided) -> list[str]:
    """Caps whose provider count fell since the baseline was taken."""
    return sorted(c for c, n in baseline.items() if len(provided.get(c, [])) < n)
'''

CAPS_CONSISTENCY_PY = '''#!/usr/bin/env python3
"""Assert modules_lint and caps_matrix reach the same verdict.

They share scripts/capreg.py, so a disagreement means one of them is not using
it. Exit 0 both pass, 2 both fail (agreement, red gate), 3 they disagree or the
tree is unshaped. A disagreement is always reported, never averaged.
"""
import subprocess
import sys
from pathlib import Path

LINT = Path("scripts/modules_lint.py")
MATRIX = Path("scripts/caps_matrix.py")


def verdict(script: Path) -> tuple[int, str]:
    if not script.exists():
        return 3, f"{script} missing"
    proc = subprocess.run([sys.executable, str(script)],
                          capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    a, a_out = verdict(LINT)
    b, b_out = verdict(MATRIX)

    if a != b:
        print("LINT DISAGREEMENT — the two parsers are not the same parser")
        print(f"  modules_lint -> {a}")
        print(f"  caps_matrix  -> {b}")
        for out in (a_out, b_out):
            for line in out.splitlines()[-6:]:
                print(f"    {line}")
        return 3

    if a == 0:
        print("both lints agree: clean")
        return 0

    print(f"both lints agree: violation (exit {a})")
    for line in b_out.splitlines()[-8:]:
        print(f"  {line}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
'''

HANDOFF_PY = '''#!/usr/bin/env python3
"""Extract the handoff section of docs/PLAN.md into docs/HANDOFF.md."""
import os, re, sys
from pathlib import Path

PLAN = Path("docs/PLAN.md")
OUT = Path("docs/HANDOFF.md")
HEAD = re.compile(r"^## " + os.environ.get("HANDOFF_SECTION", r"60\\."), re.M)


def extract() -> str:
    text = PLAN.read_text(encoding="utf-8")
    m = HEAD.search(text)
    if not m:
        sys.exit("PRECONDITION: handoff section not found in docs/PLAN.md")
    body = text[m.start():].rstrip() + "\\n"
    if len(body) < 200:
        sys.exit("PRECONDITION: handoff section suspiciously short")
    return body


def main() -> int:
    body = extract()
    if "--check" in sys.argv:
        if not OUT.exists():
            print("PRECONDITION: docs/HANDOFF.md missing", file=sys.stderr)
            return 3
        if OUT.read_text(encoding="utf-8") != body:
            print("PRECONDITION: HANDOFF drifted from PLAN", file=sys.stderr)
            return 3
        print("handoff in sync")
        return 0
    OUT.write_text(body, encoding="utf-8")
    print(f"wrote {OUT} ({len(body)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

REQUIRE_PY = '''#!/usr/bin/env python3
"""Phase precondition checker. Exit 3 on absence or drift. --lint validates."""
import hashlib, sys
from pathlib import Path
import yaml

PHASES = Path("build/phases.yaml")
REQUIRED = {"id", "gate", "revert"}
GATES = {f"G{i}" for i in range(1, 25)}


def die(msg, code=3):
    print(f"PRECONDITION: {msg}", file=sys.stderr)
    sys.exit(code)


def load():
    if not PHASES.exists():
        die(f"{PHASES} missing")
    data = yaml.safe_load(PHASES.read_text(encoding="utf-8")) or {}
    phases = data.get("phases")
    if not isinstance(phases, list) or not phases:
        die("phases.yaml has no phases list")
    return phases


def lint(phases):
    ids = [p.get("id") for p in phases]
    if len(ids) != len(set(ids)):
        die("duplicate phase id")
    for p in phases:
        missing = REQUIRED - set(p)
        if missing:
            die(f"{p.get('id', '?')}: missing {sorted(missing)}")
        if p["gate"] not in GATES:
            die(f"{p['id']}: unknown gate {p['gate']}")
        produces = {x if isinstance(x, str) else x["path"] for x in p.get("produces", [])}
        requires = {x["path"] for x in p.get("requires", [])}
        if produces & requires:
            die(f"{p['id']}: requires what it produces")
        if p["id"] != "P0" and "docs/HANDOFF.md" not in requires:
            die(f"{p['id']}: must require docs/HANDOFF.md")
    order = {pid: i for i, pid in enumerate(ids)}
    if "P8" not in order:
        die("P8 missing")
    for pid in ids:
        if pid.startswith("R") and order[pid] < order["P8"]:
            die(f"{pid}: R-phase before P8")
    print(f"phases.yaml valid ({len(ids)} phases)")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(phase_id):
    phases = {p["id"]: p for p in load()}
    if phase_id not in phases:
        die(f"unknown phase {phase_id}")
    ph = phases[phase_id]
    for req in ph.get("requires", []):
        path = Path(req["path"])
        if not path.exists():
            die(f"{phase_id} requires {path}")
        if req.get("sha256") and sha(path) != req["sha256"]:
            die(f"{path} drifted since {phase_id} was planned")
    for entry in ph.get("requires_empty", []):
        p = Path(entry)
        if p.is_file() and p.stat().st_size:
            die(f"{entry} must be empty before {phase_id}")
        if p.is_dir() and any(p.iterdir()):
            die(f"{entry} must be empty before {phase_id}")
    print(f"{phase_id}: preconditions satisfied")


if __name__ == "__main__":
    if "--lint" in sys.argv:
        lint(load())
    elif len(sys.argv) > 1:
        check(sys.argv[1])
    else:
        die("usage: require.py <phase> | --lint")
'''

BOOTSTRAP_CHECK_PY = '''#!/usr/bin/env python3
"""Verify generated tooling matches .bootstrap-state. Exit 1 on tamper."""
import hashlib, sys
from pathlib import Path

STATE = Path(".bootstrap-state")
if not STATE.exists():
    sys.exit("PRECONDITION: .bootstrap-state missing — run bootstrap")

bad = 0
for line in STATE.read_text().splitlines():
    if not line.strip():
        continue
    want, path = line.split(None, 1)
    p = Path(path)
    if not p.exists():
        print(f"missing: {path}")
        bad = 1
        continue
    if hashlib.sha256(p.read_bytes()).hexdigest() != want:
        print(f"modified: {path}")
        bad = 1
sys.exit(1 if bad else 0)
'''

OPENAPI_SNAPSHOT_PY = '''#!/usr/bin/env python3
"""Freeze the Flask URL map before dashboard_server.py is split into blueprints."""
import hashlib, json, sys
from pathlib import Path

SPEC = Path("docs/api/openapi.yaml")
ROUTES = Path("build/openapi.routes.json")
SHA = Path("build/openapi.sha256")

CANDIDATES = (
    ("pegasus.ui.web.server", "app"), ("pegasus.ui.web.server", "create_app"),
    ("pegasus.ui.api.app", "app"), ("pegasus.ui.api.app", "create_app"),
    ("dashboard_server", "app"),
)


def load_app():
    last = "no candidate module imported"
    for mod, attr in CANDIDATES:
        try:
            m = __import__(mod, fromlist=[attr])
        except Exception as exc:
            last = f"{mod}: {exc}"
            continue
        obj = getattr(m, attr, None)
        if obj is None:
            last = f"{mod}.{attr} missing"
            continue
        try:
            return obj() if attr == "create_app" else obj
        except Exception as exc:
            last = f"{mod}.{attr}() raised {exc}"
    sys.exit(f"PRECONDITION: cannot import app — {last}")


def collect(app):
    out = []
    for rule in app.url_map.iter_rules():
        methods = sorted(rule.methods - {"HEAD", "OPTIONS"})
        if not methods:
            continue
        out.append({"rule": str(rule), "methods": methods,
                    "endpoint": rule.endpoint, "args": sorted(rule.arguments)})
    out.sort(key=lambda r: (r["rule"], r["methods"]))
    return out


def main() -> int:
    routes = collect(load_app())
    if not routes:
        sys.exit("PRECONDITION: url_map is empty")
    ROUTES.parent.mkdir(parents=True, exist_ok=True)
    ROUTES.write_text(json.dumps(routes, indent=2) + "\\n", encoding="utf-8")
    lines = ["openapi: 3.0.3", "info:", "  title: Pegasus", "  version: snapshot", "paths:"]
    for r in routes:
        lines.append(f"  {r['rule']}:")
        for m in r["methods"]:
            lines += [f"    {m.lower()}:", f"      operationId: {r['endpoint']}",
                      "      responses:", "        '200': {description: ok}"]
    SPEC.parent.mkdir(parents=True, exist_ok=True)
    SPEC.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    digest = hashlib.sha256()
    for p in (SPEC, ROUTES):
        digest.update(p.read_bytes())
    SHA.write_text(digest.hexdigest() + "  openapi\\n", encoding="utf-8")
    print(f"{len(routes)} routes frozen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

MODULE_NEW_PY = '''#!/usr/bin/env python3
"""Scaffold a module: manifest, method, schema, fixture, contract test.

Replaces the absent pegasus.modules.postex.scaffold. Exit 3 on bad input.
"""
import json, re, sys
from pathlib import Path

ROOT = Path("pegasus/modules")
BLASTS = ("readonly", "stateful", "destructive", "irreversible")
COSTS = ("cheap", "moderate", "expensive")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")

MODULE_PY = \'\'\'"""{mid} module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BLAST = "{blast}"
COST = "{cost}"
REQUIRES_CAPS: set[str] = set()
SCHEMA = Path(__file__).with_name("schema.json")


def schema() -> dict[str, Any]:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def run(ctx: Any, target: str, **kw: Any) -> dict[str, Any]:
    """Return the envelope. Device-side failure is ok=False, never an exception."""
    return {{
        "ok": True, "module": "{mid}", "target": target,
        "started": None, "finished": None, "requires_root": False,
        "steps": [], "artifacts": [], "findings": {{}}, "errors": [],
    }}
\'\'\'

PLUGIN_PY = \'\'\'"""{mid} plugin registration."""

from __future__ import annotations

from typing import Any

from .module import BLAST, COST, run

NAME = "{mid}"


def register(registry: Any) -> None:
    registry.register(NAME, run, blast=BLAST, cost=COST)
\'\'\'


def schema_for(mid: str) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"{mid} result envelope", "type": "object",
        "required": ["ok", "module", "target", "steps", "artifacts", "findings", "errors"],
        "properties": {
            "ok": {"type": "boolean"}, "module": {"const": mid},
            "target": {"type": "string"}, "requires_root": {"type": "boolean"},
            "steps": {"type": "array"}, "artifacts": {"type": "array"},
            "findings": {"type": "object"},
            "errors": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": True,
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a.split("=", 1)[0]: a.split("=", 1)[1]
             for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    if not args:
        sys.exit("PRECONDITION: usage: module_new.py <id> [--blast=B] [--cost=C]")
    mid = args[0]
    if not ID_RE.match(mid):
        sys.exit(f"PRECONDITION: bad id {mid!r}")
    blast, cost = flags.get("--blast", "readonly"), flags.get("--cost", "cheap")
    if blast not in BLASTS or cost not in COSTS:
        sys.exit("PRECONDITION: bad blast or cost")
    dest = ROOT / mid
    if dest.exists():
        sys.exit(f"PRECONDITION: {dest} exists")
    dest.mkdir(parents=True)
    (dest / "__init__.py").write_text("", encoding="utf-8")
    (dest / "module.py").write_text(
        MODULE_PY.format(mid=mid, blast=blast, cost=cost), encoding="utf-8")
    (dest / "plugin.py").write_text(PLUGIN_PY.format(mid=mid), encoding="utf-8")
    (dest / "schema.json").write_text(
        json.dumps(schema_for(mid), indent=2) + "\\n", encoding="utf-8")
    print(f"created {dest} (blast={blast} cost={cost})")
    print(f"map row to add: {dest}/ | KEEP | new module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

PARITY_PY = '''#!/usr/bin/env python3
"""Diff capability names declared in registries against those in README."""
import re, sys
from pathlib import Path

REGISTRIES = ("pegasus/core/plugin/modules/base.py", "pegasus/modules/base.py",
              "weapons/registry.py", "exploits/registry.py", "c2/registry.py",
              "rat/commands.py")
README, OUT = Path("README.md"), Path("build/parity.diff")
REG_RE = re.compile(r"""register\\(\\s*["']([a-z][a-z0-9_]*)["']""")
CAP_RE = re.compile(r"(?m)^CAPABILITIES\\s*[:=].*$")
NAME_RE = re.compile(r"""["']([a-z][a-z0-9_]{2,})["']""")
DOC_RE = re.compile(r"`([a-z][a-z0-9_]{2,})`")


def declared() -> set[str]:
    names: set[str] = set()
    for rel in REGISTRIES:
        p = Path(rel)
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        names |= set(REG_RE.findall(text))
        for line in CAP_RE.findall(text):
            names |= set(NAME_RE.findall(line))
    return names


def main() -> int:
    found = [r for r in REGISTRIES if Path(r).exists()]
    if not found:
        sys.exit("PRECONDITION: no registry file found")
    if not README.exists():
        sys.exit("PRECONDITION: README.md missing")
    names = declared()
    if not names:
        sys.exit("PRECONDITION: no capability names parsed")
    documented = set(DOC_RE.findall(README.read_text(encoding="utf-8", errors="replace")))
    undoc, orphan = sorted(names - documented), sorted(documented - names)
    lines = ["# registry vs README", "", "registries: " + ", ".join(found), "",
             "## declared, not documented"]
    lines += [f"- {n}" for n in undoc] or ["- none"]
    lines += ["", "## documented, not declared (informational)"]
    lines += [f"- {n}" for n in orphan[:200]] or ["- none"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    print(f"{len(names)} declared, {len(undoc)} undocumented")
    if undoc:
        return 2
    print("parity clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

VERSION_CHECK_PY = '''#!/usr/bin/env python3
"""Assert one version everywhere. Exit 1 on drift, 3 on a missing source."""
import json, re, sys
from pathlib import Path

VERSION = Path("pegasus/VERSION")
PYPROJECTS = (Path("pyproject.toml"), Path("pegasus/pyproject.toml"))
PACKAGE = Path("pegasus/ui/web/package.json")
RESOURCES = (Path("packaging/pyinstaller/version.txt"),
             Path("packaging/pyinstaller/version-web.txt"))
NUMS = re.compile(r"\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*\\d+\\s*\\)")
STRV = re.compile(r"StringStruct\\('(?:FileVersion|ProductVersion)',\\s*'([0-9][0-9.]*)'\\)")


def main() -> int:
    if not VERSION.exists():
        sys.exit("PRECONDITION: pegasus/VERSION missing")
    want = VERSION.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\\d+\\.\\d+\\.\\d+", want):
        sys.exit(f"PRECONDITION: bad version {want!r}")
    bad = 0
    for p in PYPROJECTS:
        if not p.exists():
            continue
        m = re.search(r'(?m)^version\\s*=\\s*"([^"]+)"', p.read_text(encoding="utf-8"))
        if not m:
            print(f"  warn {p}: no version field")
        elif m.group(1) != want:
            print(f"  FAIL {p}: {m.group(1)} != {want}")
            bad = 1
        else:
            print(f"  ok   {p}")
    if PACKAGE.exists():
        got = json.loads(PACKAGE.read_text(encoding="utf-8")).get("version")
        if got != want:
            print(f"  FAIL {PACKAGE}: {got} != {want}")
            bad = 1
        else:
            print(f"  ok   {PACKAGE}")
    for p in RESOURCES:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        seen = {".".join(n) for n in NUMS.findall(text)} | set(STRV.findall(text))
        if seen != {want}:
            print(f"  FAIL {p}: {sorted(seen)} != {want}")
            bad = 1
        else:
            print(f"  ok   {p}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
'''

NO_PLATFORM_BRANCH_PY = '''#!/usr/bin/env python3
"""Fail if a module body branches on platform instead of capabilities.

Plan section 113. platform_hint is grouping only; the gate is requires_caps.
Exit 3 if no module file exists, 2 on any branch found.
"""
import re, sys
from pathlib import Path

ROOT = Path("pegasus/modules")
PATTERNS = [
    (re.compile(r"\\bif\\s+[\\w.]*platform\\s*[=!]="), "platform equality"),
    (re.compile(r"\\bis_android\\b|\\bis_ios\\b|\\bis_windows\\b"), "is_<os> helper"),
    (re.compile(r"\\bos\\.name\\s*[=!]="), "os.name comparison"),
    (re.compile(r"\\bsys\\.platform\\b"), "sys.platform"),
]
ALLOW = Path("build/noplatform.allow")


def main() -> int:
    files = sorted(ROOT.rglob("module.py")) if ROOT.exists() else []
    if not files:
        sys.exit(f"PRECONDITION: no module.py under {ROOT}")
    allow = set()
    if ALLOW.exists():
        allow = {ln.split("#")[0].strip() for ln in ALLOW.read_text().splitlines()
                 if ln.strip() and not ln.startswith("#")}
    hits = []
    for f in files:
        rel = f.as_posix()
        if rel in allow:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            code = line.split("#")[0]
            for pat, label in PATTERNS:
                if pat.search(code):
                    hits.append(f"{rel}:{i}: {label}: {code.strip()[:70]}")
                    break
    if hits:
        print("\\n".join(hits))
        print(f"\\n{len(hits)} platform branch(es) across {len(files)} module(s)")
        print("move the decision into requires_caps, or add the file to build/noplatform.allow")
        return 2
    print(f"no platform branches in {len(files)} module(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

CAPABILITY_CHECK_PY = '''#!/usr/bin/env python3
"""Dashboard is renamed Capability. Exit 3 if the web tree is absent, 2 on drift."""
import sys
from pathlib import Path

WEB = Path("pegasus/ui/web/src")
OLD, NEW = "Dashboard", "Capability"
SKIP = {"node_modules", "dist", ".vite"}


def files():
    if not WEB.exists():
        return []
    return [p for p in WEB.rglob("*")
            if p.suffix in {".tsx", ".ts", ".jsx", ".js"}
            and not SKIP & set(p.parts)]


def main() -> int:
    fs = files()
    if not fs:
        sys.exit(f"PRECONDITION: no source under {WEB}")
    stale, renamed = [], []
    for p in fs:
        text = p.read_text(encoding="utf-8", errors="replace")
        if OLD in text:
            stale.append(p.as_posix())
        if NEW in text:
            renamed.append(p.as_posix())
    if stale:
        print(f"{len(stale)} file(s) still say {OLD}:")
        for s in stale:
            print(f"  {s}")
        print(f"rename to {NEW} before P6")
        return 2
    if not renamed:
        print(f"{NEW} label not found anywhere")
        return 2
    print(f"{NEW} label present, {OLD} gone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

MODULES_LINT_PY = '''#!/usr/bin/env python3
"""Lint module manifests: ids, caps, tiers, deps, cycles, orphans.

Plan sections 115-116. Every cap comparison goes through scripts/capreg.py, the
same module caps_matrix uses, so the two lints cannot disagree about what a cap
is or whether a transport provides it. An orphan cap fails here as well as
there — a green modules_lint with a red matrix is not reachable.

Exit 3 on a malformed tree, 2 on any violation.
"""
import re, sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capreg

MANIFESTS = Path("post_exploitation/manifests")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,23}$")
REQUIRED = {"id", "title", "category", "tier"}


def load():
    if not MANIFESTS.exists():
        return None, []
    specs, errs = {}, []
    for f in sorted(MANIFESTS.glob("*.yaml")):
        raw = yaml.safe_load(f.read_text(encoding="utf-8")) or []
        if not isinstance(raw, list):
            errs.append(f"{f.name}: not a list")
            continue
        for e in raw:
            if not isinstance(e, dict):
                errs.append(f"{f.name}: entry is not a mapping")
                continue
            e["_file"] = f.name
            specs[e.get("id", "?")] = e
    return specs, errs


def main() -> int:
    try:
        known = set(capreg.cap_values())
        provided = capreg.providers()
    except capreg.Precondition as exc:
        sys.exit(f"PRECONDITION: {exc}")
    allowed = capreg.allowlist()

    specs, errs = load()
    if specs is None:
        sys.exit(f"PRECONDITION: {MANIFESTS} missing")

    for phantom in capreg.phantom_provides(known, provided):
        errs.append(f"transports/registry.yaml: phantom cap {phantom} "
                    f"(not in {capreg.CAPS})")

    waived = set()
    for sid, s in specs.items():
        where = f"{s['_file']}:{sid}"
        missing = REQUIRED - set(s)
        if missing:
            errs.append(f"{where}: missing {sorted(missing)}")
        if not ID_RE.match(sid):
            errs.append(f"{where}: bad id")
        if s.get("tier") not in (1, 2, 3):
            errs.append(f"{where}: tier must be 1, 2 or 3")
        req = s.get("requires_caps") or {}
        if not isinstance(req, dict):
            errs.append(f"{where}: requires_caps must be a mapping")
            continue
        if not req.get("all") and not req.get("any"):
            errs.append(f"{where}: needs requires_caps.all or .any")
        for field in ("all", "any", "optional"):
            for c in req.get(field) or []:
                if c not in known:
                    errs.append(f"{where}: unknown cap {c}")
                elif c not in provided:
                    if c in allowed:
                        waived.add(c)
                    else:
                        errs.append(f"{where}: orphan cap {c} "
                                    f"(no transport provides it)")
        for dep in s.get("depends_on") or []:
            if dep not in specs:
                errs.append(f"{where}: unresolved dep {dep}")

    # a cap no manifest references is still a cap with no transport
    reported = {e.split("orphan cap ", 1)[1].split(" ", 1)[0]
                for e in errs if "orphan cap " in e}
    for c in sorted(known - provided.keys() - allowed.keys()):
        if c not in reported:
            errs.append(f"cap enum: orphan cap {c} (no transport provides it)")

    graph = {k: list(v.get("depends_on") or []) for k, v in specs.items()}
    state: dict[str, int] = {}

    def visit(n: str, trail: list[str]) -> None:
        if state.get(n) == 1:
            errs.append("cycle: " + " -> ".join(trail + [n]))
            return
        if state.get(n) == 2:
            return
        state[n] = 1
        for d in graph.get(n, []):
            visit(d, trail + [n])
        state[n] = 2

    for n in graph:
        visit(n, [])

    if errs:
        print("\\n".join(errs))
        print(f"\\n{len(errs)} violation(s) across {len(specs)} manifest(s)")
        if waived:
            print(f"waived orphans: {', '.join(sorted(waived))}")
        return 2
    tiers = {t: sum(1 for s in specs.values() if s.get("tier") == t) for t in (1, 2, 3)}
    print(f"{len(specs)} manifests valid (T1={tiers[1]} T2={tiers[2]} T3={tiers[3]})")
    if waived:
        print(f"waived orphans: {', '.join(sorted(waived))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

CAPS_MATRIX_PY = '''#!/usr/bin/env python3
"""Emit the cap-to-transport matrix; fail on an orphan or a phantom cap.

Plan sections 122 and 79. Parsing and the orphan rule both come from
scripts/capreg.py — the same module modules_lint uses, so the two agree by
construction rather than by convention.

Writes build/caps_matrix.md for humans and build/caps_matrix.json for CI.
The markdown header carries the verdict, so a file left behind by a failed run
cannot be mistaken for a passing one.

Exit 3 on a malformed tree, 2 on any blocking orphan or phantom.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capreg

MD = Path("build/caps_matrix.md")
JS = Path("build/caps_matrix.json")


def main() -> int:
    try:
        values = capreg.cap_values()
        provided = capreg.providers()
    except capreg.Precondition as exc:
        sys.exit(f"PRECONDITION: {exc}")

    allowed = capreg.allowlist()
    blocking, waived, stale = capreg.split_orphans(values, provided, allowed)
    phantoms = capreg.phantom_provides(values, provided)

    baseline = capreg.load_baseline()
    dropped = capreg.dropped_edges(baseline, provided)

    failed = bool(blocking or phantoms)
    edges = sum(len(v) for v in provided.values())
    status = "FAIL" if failed else "PASS"

    rows = [f"# Capability matrix", "",
            f"STATUS: {status}",
            f"{len(values)} caps, {edges} provider edges, "
            f"{len(blocking)} blocking orphan, {len(waived)} waived, "
            f"{len(phantoms)} phantom", ""]
    if blocking:
        rows.append(f"blocking orphans: {', '.join(blocking)}")
    if phantoms:
        rows.append(f"phantom provides: {', '.join(phantoms)}")
    if stale:
        rows.append(f"stale waivers (cap now provided): {', '.join(stale)}")
    if dropped:
        rows.append(f"edge count dropped since baseline: {', '.join(dropped)}")
    rows += ["", "| Cap | Providers | Conformant | Note |", "|---|---|---|---|"]
    for c in values:
        provs = provided.get(c, [])
        conf = [n for n, p in [(t, provided.get(c, [])) for t in [] ] if False]
        note = ""
        if c in blocking:
            note = "**ORPHAN**"
        elif c in waived:
            note = f"waived: {allowed[c] or 'no reason given'}"
        if c in dropped:
            note = (note + " " if note else "") + "edge dropped"
        rows.append(f"| `{c}` | {', '.join(provs) or '**none**'} | "
                    f"{', '.join(conf) or '-'} | {note} |")
    MD.parent.mkdir(parents=True, exist_ok=True)
    MD.write_text("\\n".join(rows) + "\\n", encoding="utf-8")

    JS.write_text(json.dumps({
        "status": status,
        "caps": len(values),
        "edges": edges,
        "blocking": blocking,
        "waived": waived,
        "phantom": phantoms,
        "stale_waivers": stale,
        "dropped": dropped,
        "providers": {c: provided.get(c, []) for c in values},
    }, indent=2) + "\\n", encoding="utf-8")

    if not baseline:
        capreg.save_baseline(provided)
        rows_note = "baseline recorded"
        print(f"baseline recorded ({len(provided)} caps)")

    print(f"{len(values)} caps, {edges} provider edges, "
          f"{len(blocking)} blocking orphan, {len(phantoms)} phantom")
    if blocking:
        print("blocking orphans: " + ", ".join(blocking))
    if phantoms:
        print("phantom provides: " + ", ".join(phantoms))
    if dropped:
        print("edge count dropped: " + ", ".join(dropped))
    if waived:
        print(f"{len(waived)} waived: " + ", ".join(
            f"{c} ({allowed[c] or 'no reason given'})" for c in waived))
    if stale:
        print(f"{len(stale)} stale waiver(s): {', '.join(stale)}")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
'''

RISK_LINT_PY = '''#!/usr/bin/env python3
"""Every risk needs a detector, a ladder, a proof, an owner and an SLA.

Plan section 118. No risk without a detector; no detector without a proof.
Exit 3 on a missing register, 2 on any incomplete record.
"""
import re, sys
from pathlib import Path
import yaml

REGISTER = Path("risk/register.yaml")
REQUIRED = {"id", "title", "area", "severity", "detector", "proof", "owner", "sla_hours"}
AREAS = {"device", "data", "truth", "crypto", "infra", "ops"}
SEVERITIES = {"critical", "high", "medium", "low"}
ID_RE = re.compile(r"^R-[A-Z]+-\\d{2}$")


def main() -> int:
    if not REGISTER.exists():
        sys.exit(f"PRECONDITION: {REGISTER} missing")
    records = yaml.safe_load(REGISTER.read_text(encoding="utf-8")) or []
    if not isinstance(records, list) or not records:
        sys.exit("PRECONDITION: register is empty")
    errs, seen = [], set()
    for r in records:
        rid = r.get("id", "?")
        missing = REQUIRED - set(r)
        if missing:
            errs.append(f"{rid}: missing {sorted(missing)}")
        if not ID_RE.match(str(rid)):
            errs.append(f"{rid}: bad id shape")
        if rid in seen:
            errs.append(f"{rid}: duplicate")
        seen.add(rid)
        if r.get("area") not in AREAS:
            errs.append(f"{rid}: bad area")
        if r.get("severity") not in SEVERITIES:
            errs.append(f"{rid}: bad severity")
        if not r.get("ladder"):
            errs.append(f"{rid}: no ladder")
        if not r.get("auto"):
            errs.append(f"{rid}: no auto actions")
        proof = r.get("proof")
        if proof and not Path(str(proof)).exists():
            errs.append(f"{rid}: proof missing on disk: {proof}")
    if errs:
        print("\\n".join(errs))
        print(f"\\n{len(errs)} violation(s) across {len(records)} record(s)")
        return 2
    by_sev = {s: sum(1 for r in records if r.get("severity") == s) for s in SEVERITIES}
    print(f"{len(records)} risks valid (critical={by_sev['critical']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

AUDIT_DERIVE_PY = '''#!/usr/bin/env python3
"""Derive the module percentage. Never declared, always computed.

Plan section 119. implemented = tier<3 + method + fixture + satisfiable cap on a
conformant transport + passing conformance. Everything else is declared.
--check fails if build/audit.md drifted from a recomputation.

A T1/T2 module with no fixture lands in `unverified`, never in `implemented`, so
"code written, nothing proven" cannot masquerade as done (R-TRUTH-02).
"""
import sys
from pathlib import Path
import yaml

MANIFESTS = Path("post_exploitation/manifests")
REGISTRY = Path("transports/registry.yaml")
MODULE = Path("pegasus/modules/postexploit/module.py")
OUT = Path("build/audit.md")


def specs():
    out = []
    for f in sorted(MANIFESTS.glob("*.yaml")) if MANIFESTS.exists() else []:
        for e in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
            if isinstance(e, dict):
                out.append(e)
    return out


def conformant_caps() -> set[str]:
    if not REGISTRY.exists():
        return set()
    caps = set()
    for t in yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or []:
        if t.get("conformant"):
            caps |= set(t.get("provides") or [])
    return caps


def has_method(mid: str) -> bool:
    if not MODULE.exists():
        return False
    return f"def cmd_post_exploit_{mid}(" in MODULE.read_text(encoding="utf-8")


def has_fixture(mid: str) -> bool:
    base = Path("pegasus/tests/fixture")
    return bool(base.exists() and any(base.rglob(f"{mid}*")))


def derive() -> dict:
    all_specs, caps = specs(), conformant_caps()
    t = {"total": len(all_specs), "implemented": 0, "partial": 0,
         "unverified": 0, "declared": 0}
    for s in all_specs:
        mid, tier = s.get("id", "?"), s.get("tier", 3)
        if tier == 3:
            t["declared"] += 1
            continue
        need = set((s.get("requires_caps") or {}).get("all") or [])
        anyc = set((s.get("requires_caps") or {}).get("any") or [])
        if need - caps or (anyc and not (anyc & caps)):
            t["declared"] += 1
            continue
        if not has_method(mid) or not has_fixture(mid):
            t["unverified"] += 1
            continue
        t["implemented"] += 1
    t["pct"] = round(100 * t["implemented"] / t["total"], 1) if t["total"] else 0.0
    return t


def render(t: dict) -> str:
    return ("# Derived audit\\n\\n"
            "| Line | Value |\\n|---|---|\\n"
            f"| total | {t['total']} |\\n| implemented | {t['implemented']} |\\n"
            f"| partial | {t['partial']} |\\n| unverified | {t['unverified']} |\\n"
            f"| declared | {t['declared']} |\\n| **percent** | **{t['pct']}%** |\\n\\n"
            "Generated by scripts/audit_derive.py. Do not hand-edit.\\n")


def main() -> int:
    if not MANIFESTS.exists():
        sys.exit(f"PRECONDITION: {MANIFESTS} missing")
    t = derive()
    body = render(t)
    if "--check" in sys.argv:
        if not OUT.exists():
            sys.exit("PRECONDITION: build/audit.md missing — run make audit")
        if OUT.read_text(encoding="utf-8") != body:
            print("PRECONDITION: audit table drifted; run make audit", file=sys.stderr)
            return 2
        print(f"audit matches ({t['pct']}%)")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body, encoding="utf-8")
    print(f"{t['implemented']}/{t['total']} implemented ({t['pct']}%), "
          f"{t['declared']} declared, {t['unverified']} unverified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

EMIT_AGENTS_PY = '''#!/usr/bin/env python3
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
        if line and not line.startswith(("\\t", "#", ".")) and ":" in line:
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
            "installation": f"skill install {base}/skill.json"}, indent=2) + "\\n"
        out[f"{base}/pegasus-gates.json"] = json.dumps({
            "name": "pegasus-gates", "version": "1.0.0",
            "commands": [{"name": c["name"], "command": f"/{c['name']}",
                          "make": c["make"], "skill": c["skill"]}
                         for c in spec["commands"]],
            "agents": spec["agents"]}, indent=2) + "\\n"
    return out


def main():
    files = render(yaml.safe_load(SRC.read_text(encoding="utf-8")))
    if "--check" in sys.argv:
        bad = [p for p, body in files.items()
               if not Path(p).exists() or Path(p).read_text(encoding="utf-8") != body]
        if bad:
            print("PRECONDITION: adapters drifted:\\n  " + "\\n  ".join(bad), file=sys.stderr)
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
'''

VERIFY_PY = '''#!/usr/bin/env python3
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
    bad += ok(f"python {platform.python_version()}") if sys.version_info >= (3, 11) \\
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
    if f"\\n{target}:" not in Path("Makefile").read_text(encoding="utf-8"):
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
'''

TEST_AGENTS_PY = '''"""Contract: agent adapters match skills/agents.yaml and stay bounded."""
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
        if line and not line.startswith(("\\t", "#", ".")) and ":" in line:
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
    for name in ("skill.json", "pegasus-gates.json"):
        bodies = {t: Path(f".{t}-skills/{name}").read_text(encoding="utf-8") for t in TOOLS}
        assert len(set(bodies.values())) == 1, f"{name} differs across tools"


def test_adapters_in_sync():
    import subprocess
    import sys
    code = subprocess.run([sys.executable, "scripts/emit_agents.py", "--check"],
                          capture_output=True).returncode
    assert code == 0, "run: make agents"
'''

CAPS_PY = '''"""Capability taxonomy. Modules require caps; transports provide them.

A transport may not advertise a cap it fails in the conformance suite — `provides`
is derived from passes, never declared by hand.

Member NAME is the Python handle (SHELL). Member VALUE is the wire name ("shell").
Manifests and transport `provides` both use the value. scripts/capreg.py parses
this file with ast, so a reformat cannot change the parsed set.
"""
from __future__ import annotations

from enum import Enum


class Cap(str, Enum):
    SHELL = "shell"
    FILE_GET = "file.get"
    FILE_PUT = "file.put"
    FILE_LIST = "file.list"
    PKG_LIST = "pkg.list"
    PKG_INSTALL = "pkg.install"
    PROC_LIST = "proc.list"
    UI_INJECT = "ui.inject"
    SCREEN = "screen.capture"
    CAMERA = "camera"
    MIC = "mic"
    SMS = "comms.sms"
    CALLS = "comms.calls"
    CONTACTS = "comms.contacts"
    LOCATION = "pos.location"
    WIFI = "radio.wifi"
    BT = "radio.bt"
    NFC = "radio.nfc"
    SDR = "radio.sdr"
    CREDS_STORE = "creds.store"
    KEYSTORE = "creds.keystore"
    DPAPI = "creds.dpapi"
    SHADOW = "creds.shadow"
    SAM = "creds.sam"
    LSASS = "creds.lsass"
    REGISTRY = "os.registry"
    SYSTEMD = "os.systemd"
    LAUNCHD = "os.launchd"
    CRON = "os.cron"
    MQTT = "proto.mqtt"
    COAP = "proto.coap"
    TR069 = "proto.tr069"
    SNMP = "proto.snmp"
    MODBUS = "proto.modbus"
    DNP3 = "proto.dnp3"
    S7 = "proto.s7"
    RTSP = "proto.rtsp"
    ONVIF = "proto.onvif"
    MAVLINK = "proto.mavlink"
    CAN = "vehicle.can"
    OBD = "vehicle.obd"
    SMB = "net.smb"
    WMI = "net.wmi"
    RDP = "net.rdp"
    SSH = "net.ssh"
    LDAP = "net.ldap"
    ADB = "net.adb"
    IDEVICE = "net.idevice"
    AGENT = "agent.rpc"
    PIVOT = "net.pivot"


READ_CAPS = frozenset({
    Cap.FILE_GET, Cap.FILE_LIST, Cap.PROC_LIST, Cap.PKG_LIST, Cap.SMS,
    Cap.CALLS, Cap.CONTACTS, Cap.LOCATION, Cap.WIFI, Cap.SCREEN,
})

WRITE_CAPS = frozenset({
    Cap.FILE_PUT, Cap.PKG_INSTALL, Cap.UI_INJECT, Cap.CREDS_STORE, Cap.CAMERA,
    Cap.MIC, Cap.KEYSTORE, Cap.DPAPI, Cap.SAM, Cap.LSASS, Cap.SHADOW,
})

DESTRUCTIVE_CAPS = frozenset({
    Cap.MODBUS, Cap.SNMP, Cap.CAN, Cap.OBD, Cap.MAVLINK, Cap.ONVIF,
})

ROLE_CAPS = {
    "analyst": READ_CAPS,
    "operator": READ_CAPS | WRITE_CAPS,
    "supervisor": READ_CAPS | WRITE_CAPS | DESTRUCTIVE_CAPS,
    "administrator": frozenset(Cap),
}
'''

HOST_PY = '''"""Host model. A host is any target: phone, laptop, router, camera, PLC, drone."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from core.caps import Cap


class HostKind(str, Enum):
    ANDROID = "android"; IOS = "ios"; WINDOWS = "windows"; LINUX = "linux"
    MACOS = "macos"; IOT = "iot"; ROUTER = "router"; CAMERA = "camera"
    ICS = "ics"; DRONE = "drone"; SENSOR = "sensor"


class Trust(str, Enum):
    UNVERIFIED = "unverified"   # discovery only; read caps
    PINNED = "pinned"           # key or pairing record; non-destructive
    VERIFIED = "verified"       # signed attestation; destructive allowed
    DEMOTED = "demoted"         # conformance failure; drops one level


@dataclass
class Host:
    id: str
    kind: HostKind
    os_hint: str | None = None
    transports: list[str] = field(default_factory=list)
    caps: set[Cap] = field(default_factory=set)
    reachable_via: str | None = None
    trust: Trust = Trust.UNVERIFIED

    def allows(self, caps: set[Cap]) -> bool:
        return caps <= self.caps
'''

TRANSPORT_PY = '''"""Transport ABC and probe result. `provides` comes from conformance passes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.caps import Cap
from core.host import Host


class TransportError(Exception):
    pass


class CapUnavailable(TransportError):
    def __init__(self, cap: Cap):
        super().__init__(f"no transport provides {cap}")
        self.cap = cap


@dataclass
class Probe:
    ok: bool
    reason: str = ""
    caps: set[Cap] = field(default_factory=set)

    @classmethod
    def yes(cls) -> "Probe":
        return cls(True)

    @classmethod
    def no(cls, reason: str) -> "Probe":
        return cls(False, reason)

    def cap(self, *caps: Cap) -> "Probe":
        self.caps |= set(caps)
        return self

    def drop(self, *caps: Cap) -> "Probe":
        self.caps -= set(caps)
        return self


class Transport(ABC):
    name: str
    provides: frozenset[Cap]
    cost: int = 50          # lower preferred: adb=10, ssh=20, pivot=60

    @abstractmethod
    async def probe(self, host: Host) -> Probe: ...

    @abstractmethod
    async def open(self, host: Host, lease_id: str) -> "Session": ...
'''

SPEC_PY_SRC = '''"""Module manifest schema. A T1/T2 manifest without a method is an import error."""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from core.caps import Cap


class Status(str, Enum):
    OK = "ok"; PARTIAL = "partial"; FAILED = "failed"


class CapRequirement(BaseModel):
    all: set[Cap] = set()
    any: set[Cap] = set()
    optional: set[Cap] = set()

    def satisfiable(self, have: set[Cap]) -> bool:
        return self.all <= have and (not self.any or bool(self.any & have))

    def absent(self, have: set[Cap]) -> set[Cap]:
        if self.any and not (self.any & have):
            return (self.all - have) | self.any
        return self.all - have


class Requires(BaseModel):
    root: bool = False
    bins: list[str] = []


class ModuleSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,23}$")
    title: str
    category: str
    tier: Literal[1, 2, 3]
    requires_caps: CapRequirement
    depends_on: list[str] = []
    destructive: bool = False
    timeout: int = Field(default=60, ge=5, le=3600)
    artifacts: list[str] = []
    platform_hint: list[str] = []      # grouping only, never a gate
    requires: Requires = Requires()
    chains: list[str] = []

    @field_validator("requires_caps")
    @classmethod
    def needs_a_cap(cls, v: CapRequirement) -> CapRequirement:
        if not v.all and not v.any:
            raise ValueError("requires_caps needs all or any")
        return v

    @property
    def method(self) -> str:
        return f"cmd_post_exploit_{self.id}"


class DuplicateModule(Exception):
    pass


class MissingImplementation(Exception):
    pass


def make_stub(spec: ModuleSpec):
    def stub(self, host_id: str, **kw):
        return self.result(spec.id).partial("not_implemented")

    stub.__name__ = spec.method
    stub.not_implemented = True
    return stub


def load(root: Path, cls) -> dict[str, ModuleSpec]:
    specs: dict[str, ModuleSpec] = {}
    for f in sorted(root.glob("*.yaml")):
        for raw in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
            spec = ModuleSpec(**raw)
            if spec.id in specs:
                raise DuplicateModule(spec.id)
            if spec.tier in (1, 2) and not hasattr(cls, spec.method):
                raise MissingImplementation(spec.id, spec.method)
            if spec.tier == 3 and not hasattr(cls, spec.method):
                setattr(cls, spec.method, make_stub(spec))
            specs[spec.id] = spec
    return specs


def lint_ids(root: Path) -> list[str]:
    errs, seen = [], set()
    for f in sorted(root.glob("*.yaml")):
        for raw in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
            mid = raw.get("id", "?")
            if mid in seen:
                errs.append(f"duplicate {mid}")
            seen.add(mid)
    return errs
'''

TAXONOMY_PY = '''"""Delivery taxonomy. Stamped on every vector; drives the fingerprint shortlist."""
from __future__ import annotations

from enum import Enum


class Class(str, Enum):
    TRIGGERED = "triggered"                  # one-click, needs interaction
    COVERT = "covert"                        # zero-click
    TNE = "tactical_network_element"         # MITM injection
    INLINE = "inline"                        # inline network injection
    PHYSICAL = "physical"                    # hands-on
    RANGE = "within_range"                   # radio, partly redacted upstream


LABEL = {
    Class.TRIGGERED: "Triggered", Class.COVERT: "Covert",
    Class.TNE: "Tactical Network Element", Class.INLINE: "Inline",
    Class.PHYSICAL: "Physical", Class.RANGE: "Within range",
}


def label(os_name: str, cls: Class) -> str:
    """Render 'iOS Covert', 'Android Triggered' for the dashboard."""
    return f"{os_name} {LABEL[cls]}"


REDACTED = {Class.RANGE}      # UI must mark these partly redacted
'''

RISK_REGISTER = """# One record per risk. Every field mandatory: no risk without a detector,
# no detector without a proof test that makes it fire.
- {id: R-DEV-01, title: content query deprecated on A13+, area: device, severity: high,
   detector: probes.content_query_rc, ladder: [content_query, sqlite_pull, provider_read],
   auto: [fallback, profile_write, alert_if_all_fail],
   proof: tests/device/test_sms_paths.py, owner: collection, sla_hours: 24,
   budget: {max_fail_rate: 0.15, window: 7d}}
- {id: R-DEV-02, title: /dev/input SELinux-gated, area: device, severity: medium,
   detector: probes.input_readable, ladder: [direct, su_chmod, root_required],
   auto: [degrade, remediation_hint], proof: tests/device/test_input_probe.py,
   owner: capture, sla_hours: 48}
- {id: R-DEV-03, title: keylogger shim dies on reboot, area: device, severity: high,
   detector: probes.shim_absent, ladder: [supervisor_restart, hook_reinstall, degrade],
   auto: [self_heal, persistence_assert, escalate_after_5],
   proof: tests/device/test_shim_survival.py, owner: capture, sla_hours: 12}
- {id: R-DATA-01, title: auto-pull thrash on large DB, area: data, severity: high,
   detector: metrics.pull_p95, ladder: [delta_pull, adaptive_interval, coalesce],
   auto: [backoff, alert], proof: tests/perf/test_pull_storm.py, owner: data,
   sla_hours: 24, budget: {max_fail_rate: 0.10, window: 7d}}
- {id: R-TRUTH-01, title: unvalidated exploit auto-fires, area: truth, severity: critical,
   detector: truth.autofire_check, ladder: [block, demote], auto: [block_autofire, issue],
   proof: tests/truth/test_promotion.py, owner: orchestrator, sla_hours: 4}
- {id: R-TRUTH-02, title: declared percentages drift, area: truth, severity: high,
   detector: audit.table_match, ladder: [regenerate], auto: [ci_fail, regenerate],
   proof: tests/truth/test_audit_derivation.py, owner: platform, sla_hours: 24}
- {id: R-TRUTH-03, title: the two cap lints disagree, area: truth, severity: high,
   detector: caps.consistency, ladder: [report, block], auto: [ci_fail, block],
   proof: tests/caps/test_consistency.py, owner: platform, sla_hours: 12}
- {id: R-CRYPTO-01, title: cosmetic crypto, area: crypto, severity: critical,
   detector: crypto.selftest, ladder: [refuse_start, xor_fallback], auto: [hard_fail, banner],
   proof: tests/crypto/test_selftest.py, owner: crypto, sla_hours: 1}
- {id: R-CRYPTO-02, title: tampered export bundle, area: crypto, severity: critical,
   detector: crypto.verify_bundle, ladder: [abort_download, name_artifact],
   auto: [abort, page], proof: tests/crypto/test_bundle_sig.py, owner: crypto, sla_hours: 1}
- {id: R-INFRA-01, title: attribution leak, area: infra, severity: critical,
   detector: infra.egress_mismatch, ladder: [quarantine_node, rotate, page],
   auto: [quarantine, page], proof: tests/infra/test_egress.py, owner: infra, sla_hours: 1}
- {id: R-OPS-01, title: multi-device pull storm, area: ops, severity: high,
   detector: scheduler.queue_depth, ladder: [serialize, jitter, debounce],
   auto: [throttle], proof: tests/perf/test_multi_connect.py, owner: ops, sla_hours: 24}
- {id: R-OPS-02, title: destructive action without undo, area: ops, severity: high,
   detector: ops.rollback_available, ladder: [presnapshot, plan_mode, mark_risky],
   auto: [presnapshot], proof: tests/ops/test_rollback.py, owner: ops, sla_hours: 12}
- {id: R-CAP-01, title: implant advertises caps it lacks, area: truth, severity: high,
   detector: probes.cap_lie, ladder: [clamp, demote_build, alert],
   auto: [clamp, issue], proof: tests/caps/test_cap_lie.py, owner: broker, sla_hours: 24,
   budget: {max_fail_rate: 0.01, window: 7d}}
- {id: R-CAP-06, title: partial rate masks breakage, area: truth, severity: high,
   detector: metrics.partial_rate, ladder: [family_review, demote_tier],
   auto: [alert, demote], proof: tests/audit/test_partial_masking.py, owner: platform,
   sla_hours: 12, budget: {max_fail_rate: 0.15, window: 7d}}
"""

TRANSPORT_REGISTRY = """# provides is written from conformance passes, never declared by hand.
# conformant flips true only when the suite is green for that transport.
# Every value must exist in core/caps.py; capreg reports a typo as a phantom.
- {name: adb, cost: 10, conformant: false,
   provides: [net.adb, shell, file.get, file.put, file.list, pkg.list, pkg.install,
              proc.list, ui.inject, screen.capture, comms.sms, comms.calls,
              comms.contacts, pos.location, radio.wifi, radio.bt, radio.nfc,
              creds.keystore, os.cron, camera, mic]}
- {name: idevice, cost: 12, conformant: false,
   provides: [net.idevice, file.get, file.put, file.list, pkg.list, screen.capture]}
- {name: agent.rpc, cost: 40, conformant: false,
   provides: [agent.rpc, shell, file.get, file.put, file.list, proc.list, pkg.list,
              creds.store, creds.sam, creds.lsass, creds.dpapi, net.pivot]}
- {name: ssh, cost: 20, conformant: false,
   provides: [net.ssh, shell, file.get, file.list, proc.list, os.systemd, os.cron,
              os.launchd, creds.shadow, net.pivot]}
- {name: smb, cost: 30, conformant: false,
   provides: [net.smb, file.get, file.list]}
- {name: wmi, cost: 35, conformant: false,
   provides: [net.wmi, proc.list, pkg.list, os.registry]}
- {name: rdp, cost: 45, conformant: false,
   provides: [net.rdp, ui.inject, screen.capture]}
- {name: ldap, cost: 40, conformant: false,
   provides: [net.ldap]}
- {name: snmp, cost: 60, conformant: false,
   provides: [proto.snmp]}
- {name: mqtt, cost: 60, conformant: false,
   provides: [proto.mqtt]}
- {name: coap, cost: 60, conformant: false,
   provides: [proto.coap]}
- {name: tr069, cost: 60, conformant: false,
   provides: [proto.tr069]}
- {name: modbus, cost: 65, conformant: false,
   provides: [proto.modbus]}
- {name: dnp3, cost: 65, conformant: false,
   provides: [proto.dnp3]}
- {name: s7, cost: 65, conformant: false,
   provides: [proto.s7]}
- {name: rtsp, cost: 50, conformant: false,
   provides: [proto.rtsp, screen.capture]}
- {name: onvif, cost: 55, conformant: false,
   provides: [proto.onvif, camera]}
- {name: mavlink, cost: 55, conformant: false,
   provides: [proto.mavlink, pos.location]}
- {name: can, cost: 70, conformant: false,
   provides: [vehicle.can]}
- {name: obd, cost: 70, conformant: false,
   provides: [vehicle.obd]}
- {name: bt, cost: 25, conformant: false,
   provides: [radio.bt]}
- {name: nfc, cost: 25, conformant: false,
   provides: [radio.nfc]}
- {name: sdr, cost: 80, conformant: false,
   provides: [radio.sdr]}
"""

CAPS_ALLOW = """# Caps deliberately without a transport provider.
#
# Format: <cap-value>   # <reason>
#
# A cap listed here reports as WAIVED in the matrix and does not fail either
# lint. A waiver for a cap that IS provided reports as STALE — remove it.
# The baseline in build/caps_baseline.json still records the edge count, so
# waiving an orphan does not hide a later provider regression.
"""

BUILD_MATRIX = """# Implant build matrix. hello caps are clamped to the build row (plan 77).
- {build: android-min,
   caps: [agent.rpc, shell, file.get, file.list, proc.list, pkg.list]}
- {build: android-full,
   caps: [agent.rpc, shell, file.get, file.put, file.list, proc.list, pkg.list,
          comms.sms, comms.calls, comms.contacts, pos.location, radio.wifi,
          screen.capture, camera, mic, creds.keystore, os.cron]}
- {build: windows-svc,
   caps: [agent.rpc, shell, file.get, file.list, proc.list, os.registry,
          creds.sam, creds.dpapi]}
- {build: linux-svc,
   caps: [agent.rpc, shell, file.get, file.put, file.list, proc.list,
          os.systemd, os.cron, creds.shadow]}
- {build: ios-mdm,
   caps: [agent.rpc, pos.location, screen.capture]}
"""

MANIFESTS = {
    "01_credentials.yaml": """# family: credentials
- id: credential_manager
  title: OS credential store enumeration
  category: credentials
  tier: 3
  requires_caps: {all: [creds.store]}
  timeout: 120
  artifacts: [json]
- id: browser_creds
  title: Browser credential tables
  category: credentials
  tier: 3
  requires_caps: {all: [file.get]}
  depends_on: []
  timeout: 120
  artifacts: [json]
  platform_hint: [android, windows, linux]
- id: sam_dump
  title: SAM hive dump
  category: credentials
  tier: 3
  requires_caps: {all: [creds.sam], any: [agent.rpc, net.smb]}
  depends_on: [credential_manager]
  timeout: 180
  artifacts: [json, csv]
  platform_hint: [windows]
  requires: {root: true, bins: [secretsdump.py]}
- id: lsass_minidump
  title: LSASS memory dump
  category: credentials
  tier: 3
  requires_caps: {all: [creds.lsass]}
  depends_on: [priv_esc_recon]
  timeout: 240
  artifacts: [zip]
  platform_hint: [windows]
- id: shadow_hash_dump
  title: /etc/shadow extraction
  category: credentials
  tier: 3
  requires_caps: {all: [creds.shadow]}
  timeout: 90
  artifacts: [txt]
  platform_hint: [linux]
- id: totp_seeds
  title: TOTP seed extraction
  category: credentials
  tier: 3
  requires_caps: {all: [file.get]}
  timeout: 150
  artifacts: [json]
  platform_hint: [android]
""",
    "02_wallets.yaml": """# family: wallets
- id: seed_phrase_extract
  title: BIP39 seed scan with local checksum
  category: wallets
  tier: 3
  requires_caps: {all: [file.get]}
  timeout: 180
  artifacts: [json]
  platform_hint: [android]
- id: wallet_dat_scan
  title: wallet.dat sweep
  category: wallets
  tier: 3
  requires_caps: {all: [file.get]}
  timeout: 180
  artifacts: [json]
  platform_hint: [windows, linux]
- id: address_harvest
  title: Address harvest from pulled artifacts
  category: wallets
  tier: 3
  requires_caps: {all: [file.get]}
  timeout: 120
  artifacts: [csv]
""",
    "03_hash_hunt.yaml": """# family: hash_hunt
- id: kdbx_hunt
  title: KeePass vault sweep
  category: hash_hunt
  tier: 3
  requires_caps: {all: [file.get]}
  timeout: 150
  artifacts: [json]
- id: pem_pfx_hunt
  title: PEM and PFX sweep
  category: hash_hunt
  tier: 3
  requires_caps: {all: [file.get]}
  timeout: 150
  artifacts: [json]
""",
    "04_privesc_root.yaml": """# family: privesc_root
- id: priv_esc_recon
  title: Escalation technique recon
  category: privesc_root
  tier: 3
  requires_caps: {all: [shell]}
  timeout: 240
  artifacts: [json]
  platform_hint: [android, linux, windows, macos]
- id: exploit_priv_esc
  title: Run ranked escalation technique
  category: privesc_root
  tier: 3
  requires_caps: {all: [shell]}
  depends_on: [priv_esc_recon]
  timeout: 300
  artifacts: [txt]
- id: root_device
  title: Device root via Magisk route
  category: privesc_root
  tier: 3
  requires_caps: {all: [shell]}
  depends_on: [priv_esc_recon]
  timeout: 600
  destructive: true
  platform_hint: [android]
- id: selinux_flip
  title: SELinux mode change
  category: privesc_root
  tier: 3
  requires_caps: {all: [shell]}
  timeout: 90
  destructive: true
  platform_hint: [android]
""",
    "05_persistence_stealth.yaml": """# family: persistence_stealth
- id: persist_install
  title: Install persistence mechanism
  category: persistence_stealth
  tier: 3
  requires_caps: {any: [os.cron, os.systemd, os.registry]}
  depends_on: [priv_esc_recon]
  timeout: 180
  destructive: true
- id: boot_survival_test
  title: Reboot and assert persistence
  category: persistence_stealth
  tier: 3
  requires_caps: {all: [shell]}
  depends_on: [persist_install]
  timeout: 400
  destructive: true
- id: log_wipe
  title: Log wipe
  category: persistence_stealth
  tier: 3
  requires_caps: {all: [shell]}
  timeout: 120
  destructive: true
- id: apk_wrap
  title: Repackage implant inside a host APK
  category: persistence_stealth
  tier: 3
  requires_caps: {all: [file.get, pkg.install]}
  timeout: 300
  destructive: true
  platform_hint: [android]
""",
    "06_network_lateral.yaml": """# family: network_lateral
- id: lan_scan
  title: LAN sweep
  category: network_lateral
  tier: 3
  requires_caps: {any: [shell, agent.rpc]}
  timeout: 240
  artifacts: [json]
  requires: {bins: [nmap]}
- id: smb_share_enum
  title: SMB share enumeration
  category: network_lateral
  tier: 3
  requires_caps: {all: [net.smb]}
  timeout: 120
  artifacts: [json]
  platform_hint: [windows]
- id: psexec
  title: PsExec lateral execution
  category: network_lateral
  tier: 3
  requires_caps: {all: [net.smb]}
  depends_on: [smb_share_enum]
  timeout: 180
  destructive: true
  requires: {bins: [psexec.py]}
- id: pivot_graph
  title: Pivot graph build
  category: network_lateral
  tier: 3
  requires_caps: {all: [net.pivot]}
  depends_on: [lan_scan]
  timeout: 200
  artifacts: [json]
""",
    "07_wireless.yaml": """# family: wireless
- id: wifi_scan
  title: Wi-Fi scan
  category: wireless
  tier: 3
  requires_caps: {all: [radio.wifi]}
  timeout: 120
  artifacts: [csv]
  platform_hint: [android]
- id: handshake_capture
  title: WPA handshake capture
  category: wireless
  tier: 3
  requires_caps: {all: [radio.wifi]}
  depends_on: [wifi_scan]
  timeout: 300
  artifacts: [zip]
  requires: {bins: [hcxdumptool]}
- id: bt_scan
  title: Bluetooth scan
  category: wireless
  tier: 3
  requires_caps: {all: [radio.bt]}
  timeout: 120
  artifacts: [csv]
- id: cell_tower_dump
  title: Cell tower dump
  category: wireless
  tier: 3
  requires_caps: {all: [pos.location]}
  timeout: 90
  artifacts: [json]
  platform_hint: [android]
""",
    "08_data_export.yaml": """# family: data_export — all T1-shaped, cap-gated source, streaming artifact
- id: contacts_export
  title: Contacts export
  category: data_export
  tier: 3
  requires_caps: {all: [comms.contacts]}
  timeout: 120
  artifacts: [csv, json]
- id: sms_export
  title: SMS export
  category: data_export
  tier: 3
  requires_caps: {all: [comms.sms]}
  timeout: 150
  artifacts: [csv, json]
- id: call_log_export
  title: Call log export
  category: data_export
  tier: 3
  requires_caps: {all: [comms.calls]}
  timeout: 120
  artifacts: [csv, json]
- id: location_export
  title: Location history export
  category: data_export
  tier: 3
  requires_caps: {all: [pos.location]}
  timeout: 150
  artifacts: [csv, kml, gpx]
- id: all_logs_export
  title: Aggregate log export
  category: data_export
  tier: 3
  requires_caps: {all: [comms.sms, comms.calls, comms.contacts, pos.location]}
  depends_on: [contacts_export, sms_export, call_log_export, location_export]
  timeout: 400
  artifacts: [zip]
""",
}

_PROOF_SPECS = [
    ("tests/device/test_sms_paths.py", "content_query_rc", "R-DEV-01"),
    ("tests/device/test_input_probe.py", "input_readable", "R-DEV-02"),
    ("tests/device/test_shim_survival.py", "shim_absent", "R-DEV-03"),
    ("tests/perf/test_pull_storm.py", "pull_p95", "R-DATA-01"),
    ("tests/truth/test_promotion.py", "autofire_check", "R-TRUTH-01"),
    ("tests/truth/test_audit_derivation.py", "table_match", "R-TRUTH-02"),
    ("tests/caps/test_consistency.py", "consistency", "R-TRUTH-03"),
    ("tests/crypto/test_selftest.py", "selftest", "R-CRYPTO-01"),
    ("tests/crypto/test_bundle_sig.py", "verify_bundle", "R-CRYPTO-02"),
    ("tests/infra/test_egress.py", "egress_mismatch", "R-INFRA-01"),
    ("tests/perf/test_multi_connect.py", "queue_depth", "R-OPS-01"),
    ("tests/ops/test_rollback.py", "rollback_available", "R-OPS-02"),
    ("tests/caps/test_cap_lie.py", "cap_lie", "R-CAP-01"),
    ("tests/audit/test_partial_masking.py", "partial_rate", "R-CAP-06"),
]
PROOFS = {
    path: (f'import pytest\n\n\ndef test_{name}_detector_fires():\n'
           f'    pytest.skip("{rid} detector not wired yet")\n')
    for path, name, rid in _PROOF_SPECS
}

PHASES_YAML = """phases:
  - {id: P0, gate: G13, revert: "delete produced", requires: [],
     produces: [docs/PLAN.md, docs/HANDOFF.md, skills/SKILL.md, skills/agents.yaml, build/claims.frozen]}
  - {id: P1, gate: G2, revert: "git revert", requires: [{path: docs/HANDOFF.md}, {path: LICENSE, sha256: "2a06521630b1ee7725add62da05fb47f3bba6233604a402a5d5f7a3364ed8b21"}, {path: docs/LICENSE-DECISION.md}], produces: []}
  - {id: P2, gate: G2, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: [archive/root-entrypoints/DIFF.md]}
  - {id: P3a, gate: G10, revert: "delete artifacts", requires: [{path: docs/HANDOFF.md}],
     produces: [docs/api/openapi.yaml, build/openapi.routes.json, build/openapi.sha256]}
  - {id: P3b, gate: G4, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: []}
  - {id: P3c, gate: G4, revert: "git revert", requires: [{path: docs/HANDOFF.md}],
     produces: [pegasus/tests/unit, pegasus/tests/integ, pegasus/tests/contract, pegasus/tests/fixture]}
  - {id: P4, gate: G3, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: [pegasus/db/migrations]}
  - {id: P5, gate: G4, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: [docs/PROVENANCE.md]}
  - {id: P6, gate: G6, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: []}
  - {id: P7, gate: G8, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: [dist]}
  - {id: P8, gate: G13, revert: "delete tag", requires: [{path: docs/HANDOFF.md}], produces: [README.md]}
  - {id: P9, gate: G19, revert: "git revert", requires: [{path: docs/HANDOFF.md}],
     produces: [core/caps.py, core/host.py, core/transport.py]}
  - {id: P10, gate: G20, revert: "git revert", requires: [{path: docs/HANDOFF.md}],
     produces: [post_exploitation/spec.py, post_exploitation/manifests]}
  - {id: P11, gate: G21, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: [build/audit.md]}
  - {id: P12, gate: G22, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: []}
  - {id: P13, gate: G23, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: [docs/EVIDENCE.md]}
  - {id: P14, gate: G24, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: [ai/catalog.yaml]}
  - {id: R0, gate: G11, revert: "git revert", requires: [{path: docs/HANDOFF.md}],
     produces: [build/map.diff]}
  - {id: R1, gate: G2, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: []}
  - {id: R2, gate: G3, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: []}
  - {id: R3, gate: G4, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: []}
  - {id: R4, gate: G4, revert: "delete tag", requires: [{path: docs/HANDOFF.md}], produces: []}
"""

PRE_COMMIT = """#!/usr/bin/env bash
set -euo pipefail
staged=$(git diff --cached --name-only)
if printf '%s\\n' "$staged" | grep -Eq '^(docs/PLAN\\.md|skills/agents\\.yaml)$' || [ ! -s docs/HANDOFF.md ]; then
  python3 scripts/handoff.py
  git add docs/HANDOFF.md
fi
if printf '%s\\n' "$staged" | grep -qx 'skills/agents.yaml'; then
  python3 scripts/emit_agents.py
  git add .opencode-skills .mimocode-skills .zcode-skills .openfable-skills .zfable-skills
fi
python3 scripts/handoff.py --check || { echo "handoff drift — commit blocked" >&2; exit 1; }
python3 scripts/emit_agents.py --check || { echo "adapter drift — commit blocked" >&2; exit 1; }
python3 scripts/modules_lint.py || { echo "manifest invalid — commit blocked" >&2; exit 1; }
python3 scripts/caps_consistency.py || { echo "cap lints disagree — commit blocked" >&2; exit 1; }
exit 0
"""

PRE_PUSH = """#!/usr/bin/env bash
set -euo pipefail
python3 scripts/handoff.py --check      || { echo "handoff drift — push blocked" >&2; exit 1; }
python3 scripts/emit_agents.py --check  || { echo "adapter drift — push blocked" >&2; exit 1; }
python3 scripts/require.py --lint       || { echo "phases invalid — push blocked" >&2; exit 1; }
python3 scripts/version_check.py        || { echo "version drift — push blocked" >&2; exit 1; }
python3 scripts/caps_consistency.py     || { echo "cap lints disagree — push blocked" >&2; exit 1; }
python3 scripts/risk_lint.py            || { echo "risk record incomplete — push blocked" >&2; exit 1; }
python3 scripts/no_platform_branch.py   || { echo "platform branch — push blocked" >&2; exit 1; }
python3 scripts/audit_derive.py --check || { echo "audit drift — push blocked" >&2; exit 1; }
python3 scripts/bootstrap-check.py      || { echo "tooling tampered — push blocked" >&2; exit 1; }
exit 0
"""

COMMIT_MSG = """#!/usr/bin/env bash
set -euo pipefail
msg=$(head -n1 "$1")
printf '%s' "$msg" | grep -Eq '^(P[0-9][a-c]?|R[0-4]|PLAN): .+' || {
  echo "commit must start with a phase prefix, e.g. 'P11: add browser_creds'" >&2
  exit 1
}
exit 0
"""

SKILL_MD = """# Pegasus agent skills

Canonical instructions. The five adapter directories are generated from
`skills/agents.yaml`; never hand-edit them.

Rule: agent files orchestrate, scripts enforce. Every command wraps a target
that fails loudly.

Three invariants bind every skill here: capability over platform, leases over
sequencing, derived over declared.
"""

SKILLS = {
    "phase-runner.md": """# phase-runner

Run one phase, in order, stopping at the first failure.

1. `make hooks` — re-assert hooksPath.
2. `make handoff` — regenerate the brief.
3. `python3 scripts/require.py <phase>` — exit 3 means stop and report the missing path.
4. `make <gate target>` — resolve via `skills/gate-map.md`.
5. On pass, write `docs/STATUS.md`.
6. On fail, print the phase revert from `build/phases.yaml` and stop.

Never continue on a red gate. Never use `--no-verify`. Never edit
`build/phases.yaml` to make a check pass.
""",
    "definition-of-ready.md": """# definition-of-ready

Refuse the work unless every box is true. Report which are false.

- [ ] A row for every touched path exists in PLAN section 9
- [ ] A falsifier is named for every new rule
- [ ] Rollback target identified
- [ ] `requires_caps` declared — never a platform branch
- [ ] Every cap has a transport provider, or a waiver with a reason
- [ ] Tier honest: T3 if no implementation
- [ ] A risk record links to the module
- [ ] No generated file hand-edited

If any box is false, say so and stop.
""",
    "gate-map.md": """# gate-map

| Gate | Target |
|---|---|
| G1 setup · G2 test · G3 integ · G4 contract · G5 lint · G6 ui · G7 parity |
| G8 dist · G9 import · G10 openapi-snapshot · G11 map · G12 plan-lint |
| G13 handoff-check · G14 handoff-guard · G15 hooks-check · G16 bootstrap-check |
| G17 agents-check · G18 agents-lint · G19 conformance · G20 modules-lint |
| G21 audit-check · G22 replay · G23 evidence-check · G24 eval |

Confirm the gate exists, run `make <target>`, report the exit code, print the
phase revert on failure.
""",
    "map-assign.md": """# map-assign

Close `build/map.diff` to zero.

1. `make map` — writes `build/map.diff`.
2. Choose one verdict per line: KEEP MOVE MERGE DELETE ARCHIVE VENDOR GENERATE.
3. Add a row to PLAN section 9 with the verdict and a one-line reason.
4. Re-run `make map`. Repeat until empty.

Assign section 9.11 groups first. Never delete without a row.
""",
    "module-scaffold.md": """# module-scaffold

1. `make caps-matrix` — every cap you need must name a transport.
2. `make modules-lint` — must pass.
3. Add the manifest entry with `requires_caps` (values, not names) and a tier.
4. `make module-new ID=<id>` for the body, if T1 or T2.
5. Write the replay fixture.
6. `make contract` then `make audit`.

T1 with no fixture stays `unverified`. Never set T1/T2 without a method. A cap
with no provider needs a line in `build/caps_orphans.allow`, or the build stops.
""",
    "handoff-guard.md": """# handoff-guard

1. `make handoff`.
2. `make handoff-check` — must exit 0.
3. `git add docs/HANDOFF.md`.
4. Confirm `git diff --cached` shows both `PLAN.md` and `HANDOFF.md`.

Never hand-edit `docs/HANDOFF.md`.
""",
    "blocked-recovery.md": """# blocked-recovery

1. Read the failure verbatim.
2. Classify: precondition (exit 3), gate failure (exit 2), environment.
3. Precondition — satisfy it, do not edit `phases.yaml`.
4. Gate failure — fix the cause; if the gate is wrong, propose an ADR.
5. Re-run the same gate and report the diff.
6. Continue only after green.

Do not delete a check, skip a test, or use `--no-verify`.
""",
}

AGENTS_YAML = """version: 1
tools: [opencode, mimocode, zcode, openfable, zfable]
skills: [phase-runner, definition-of-ready, gate-map, map-assign, module-scaffold, handoff-guard, blocked-recovery]
commands:
  - {name: phase,      make: "require",     args: phase, skill: phase-runner}
  - {name: ready,      make: "ready-check",              skill: definition-of-ready}
  - {name: gate,       make: "gate",        args: gate,  skill: gate-map}
  - {name: map,        make: "map",                      skill: map-assign}
  - {name: handoff,    make: "handoff",                  skill: handoff-guard}
  - {name: module-new, make: "module-new",  args: id,    skill: module-scaffold}
  - {name: audit,      make: "audit",                    skill: module-scaffold}
  - {name: blocked,    make: "blocked",                  skill: blocked-recovery}
agents:
  - id: gate-runner
    max_steps: 6
    terminal_gate: G2
    may: [make test, make integ, make contract, make lint, make import]
    may_not: [edit build/phases.yaml, edit docs/PLAN.md, edit scripts/, git push]
  - id: map-auditor
    max_steps: 8
    terminal_gate: G11
    may: [make map, edit docs/PLAN.md section 9, run git ls-files]
    may_not: [edit build/, edit scripts/, git push]
  - id: module-builder
    max_steps: 7
    terminal_gate: G4
    may: [make module-new, edit post_exploitation/manifests, make contract]
    may_not: [edit core/, edit build/, git push]
  - id: manifest-auditor
    max_steps: 6
    terminal_gate: G20
    may: [make modules-lint, make audit, edit post_exploitation/manifests]
    may_not: [edit pegasus/modules, edit build/, git push]
  - id: cap-auditor
    max_steps: 5
    terminal_gate: G20
    may: [make caps-matrix, make caps-consistency, edit build/caps_orphans.allow]
    may_not: [edit core/caps.py, edit pegasus/modules, git push]
  - id: handoff-keeper
    max_steps: 3
    terminal_gate: G13
    may: [make handoff, make handoff-check, git add docs/HANDOFF.md]
    may_not: [edit docs/PLAN.md, git push]
"""

MANAGED_TARGETS = [
    "setup", "test", "integ", "contract", "lint", "ui", "parity", "dist",
    "import", "openapi-snapshot", "verify", "version-check", "map", "plan-lint",
    "require", "ready-check", "blocked", "gate", "module-new", "preflight",
    "doctor", "bootstrap-check", "agents", "agents-check", "agents-lint",
    "hooks", "hooks-check", "handoff", "handoff-check", "handoff-guard",
    "modules-lint", "audit", "audit-check", "caps-matrix", "caps-consistency",
    "caps-baseline", "risk-lint", "noplatform", "capability-check",
    "conformance", "replay", "evidence-check", "eval", "docs/HANDOFF.md",
]

MAKEFILE_BLOCK = """
PHASE ?= P0
VENV ?= .venv
PY ?= python3
BLAST ?= readonly
COST ?= cheap

docs/HANDOFF.md: docs/PLAN.md
\tpython3 scripts/handoff.py

.PHONY: setup test integ contract lint ui parity dist import openapi-snapshot
.PHONY: verify version-check map plan-lint require ready-check blocked gate
.PHONY: module-new preflight doctor bootstrap-check agents agents-check agents-lint
.PHONY: hooks hooks-check handoff handoff-check handoff-guard modules-lint audit
.PHONY: audit-check caps-matrix caps-consistency caps-baseline risk-lint noplatform
.PHONY: capability-check conformance replay evidence-check eval

setup: hooks
\tpython3 -m venv $(VENV)
\t$(VENV)/bin/python -m pip install -U pip
\t@if [ -f pyproject.toml ]; then $(VENV)/bin/pip install -e ".[all]"; \\
\t else $(VENV)/bin/pip install -e "pegasus[dev]"; fi

test:
\t$(PY) -m pytest -q pegasus/tests/unit pegasus/tests/py
integ:
\t$(PY) -m pytest -q pegasus/tests/integ -m "not live"
contract:
\t$(PY) -m pytest -q pegasus/tests/contract
lint:
\t$(PY) -m ruff check . && $(PY) -m mypy --strict pegasus
ui:
\tnpm run --prefix pegasus/ui/web build
parity:
\t$(PY) scripts/parity.py
dist:
\tbash packaging/build_all_formats.sh
import:
\t$(PY) -c "import pegasus, pegasus.modules.base"
openapi-snapshot:
\t$(PY) scripts/openapi_snapshot.py
verify:
\tpython3 scripts/verify.py --doctor
version-check:
\t$(PY) scripts/version_check.py
modules-lint:
\t$(PY) scripts/modules_lint.py
audit:
\t$(PY) scripts/audit_derive.py
audit-check:
\t$(PY) scripts/audit_derive.py --check
caps-matrix:
\t$(PY) scripts/caps_matrix.py
caps-consistency:
\t$(PY) scripts/caps_consistency.py
caps-baseline:
\t@rm -f build/caps_baseline.json
\t@$(PY) scripts/caps_matrix.py >/dev/null || true
\t@test -s build/caps_baseline.json || { echo "baseline not written"; exit 1; }
\t@echo "baseline refreshed"
risk-lint:
\t$(PY) scripts/risk_lint.py
noplatform:
\t$(PY) scripts/no_platform_branch.py
capability-check:
\t$(PY) scripts/capability_check.py
conformance:
\t$(PY) -m pytest -q pegasus/tests/conformance
replay:
\t$(PY) -m pytest -q pegasus/tests/transcripts
evidence-check:
\t$(PY) -m pytest -q pegasus/tests/contract -k evidence
eval:
\t$(PY) -m pytest -q pegasus/tests/eval
map:
\t@test -s build/map.diff || { echo "G11 FAIL: build/map.diff missing or empty"; exit 1; }
\t@if grep -n 'UNKNOWN' build/map.diff; then echo "G11 FAIL: unresolved rows above"; exit 1; fi
\t@echo "G11 PASS"
plan-lint:
\tpython3 scripts/require.py --lint
require:
\tpython3 scripts/require.py "$(PHASE)"
ready-check:
\tpython3 scripts/verify.py --ready
blocked:
\tpython3 scripts/verify.py --blocked
gate:
\tpython3 scripts/verify.py --gate "$(GATE)"
module-new:
\t$(PY) scripts/module_new.py "$(ID)" --blast=$(BLAST) --cost=$(COST)
preflight:
\tpython3 scripts/verify.py --preflight
doctor: hooks-check bootstrap-check
\tpython3 scripts/verify.py --doctor
bootstrap-check:
\tpython3 scripts/bootstrap-check.py
agents:
\tpython3 scripts/emit_agents.py
agents-check:
\tpython3 scripts/emit_agents.py --check
agents-lint:
\t$(PY) -m pytest -q pegasus/tests/contract/test_agents.py
hooks:
\tgit config core.hooksPath .githooks && chmod +x .githooks/* || true
hooks-check:
\t@test "$$(git config core.hooksPath || true)" = ".githooks" || { echo "hooksPath unset — run make hooks"; exit 1; }
\t@for f in .githooks/pre-commit .githooks/pre-push .githooks/commit-msg; do \\
\t  test -x "$$f" || { echo "$$f missing or not executable"; exit 1; }; done
handoff: docs/HANDOFF.md
handoff-check:
\tpython3 scripts/handoff.py --check
handoff-guard: handoff-check
\t@test -s docs/HANDOFF.md || { echo "HANDOFF empty"; exit 1; }
"""

PAYLOADS = {
    "scripts/capreg.py": CAPREG_PY,
    "scripts/caps_consistency.py": CAPS_CONSISTENCY_PY,
    "scripts/handoff.py": HANDOFF_PY,
    "scripts/require.py": REQUIRE_PY,
    "scripts/bootstrap-check.py": BOOTSTRAP_CHECK_PY,
    "scripts/openapi_snapshot.py": OPENAPI_SNAPSHOT_PY,
    "scripts/module_new.py": MODULE_NEW_PY,
    "scripts/parity.py": PARITY_PY,
    "scripts/version_check.py": VERSION_CHECK_PY,
    "scripts/modules_lint.py": MODULES_LINT_PY,
    "scripts/audit_derive.py": AUDIT_DERIVE_PY,
    "scripts/caps_matrix.py": CAPS_MATRIX_PY,
    "scripts/risk_lint.py": RISK_LINT_PY,
    "scripts/no_platform_branch.py": NO_PLATFORM_BRANCH_PY,
    "scripts/capability_check.py": CAPABILITY_CHECK_PY,
    "scripts/emit_agents.py": EMIT_AGENTS_PY,
    "scripts/verify.py": VERIFY_PY,
    "pegasus/tests/contract/test_agents.py": TEST_AGENTS_PY,
}

SPEC_PY = ("core/caps.py", "core/host.py", "core/transport.py",
           "post_exploitation/spec.py", "delivery/taxonomy.py")

SPECS = {
    "core/caps.py": CAPS_PY,
    "core/host.py": HOST_PY,
    "core/transport.py": TRANSPORT_PY,
    "post_exploitation/spec.py": SPEC_PY_SRC,
    "delivery/taxonomy.py": TAXONOMY_PY,
    "risk/register.yaml": RISK_REGISTER,
    "transports/registry.yaml": TRANSPORT_REGISTRY,
    "builds/matrix.yaml": BUILD_MATRIX,
    "build/caps_orphans.allow": CAPS_ALLOW,
}
for _name, _body in MANIFESTS.items():
    SPECS[f"post_exploitation/manifests/{_name}"] = _body
SPECS.update(PROOFS)


def check_drift(force: bool) -> None:
    say("0b/21 checking existing tooling")
    if not STATE.exists():
        say("    first run")
        return
    drifted = []
    for line in STATE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        want, rel = line.split(None, 1)
        path = Path(rel)
        if not path.exists():
            drifted.append(f"missing: {rel}")
        elif sha256(path) != want:
            drifted.append(f"modified: {rel}")
    if not drifted:
        say("    tooling intact")
        return
    for row in drifted:
        print(f"    {row}")
    if not force:
        die("tooling modified — rerun with --force (a backup is taken first)")
    backup = Path("build/.tooling-backup") / stamp()
    for rel in TOOLING:
        src = Path(rel)
        if src.exists():
            dst = backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    say(f"    backed up to {backup}")


def extract_version(text: str) -> str | None:
    m = SEMVER.search(text)
    return ".".join(m.groups()) if m else None


def canonical_version() -> str | None:
    if VERSION_FILE.exists():
        got = VERSION_FILE.read_text(encoding="utf-8").strip()
        if TRIPLE.match(got):
            return got
    found = []
    for rel in PYRESOURCES:
        p = Path(rel)
        if p.exists():
            got = extract_version(p.read_text(encoding="utf-8", errors="replace"))
            if got:
                found.append(got)
    if found:
        return max(found, key=lambda v: tuple(int(x) for x in v.split(".")))
    for p in (Path("pyproject.toml"), Path("pegasus/pyproject.toml")):
        if p.exists():
            m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8"))
            if m and TRIPLE.match(m.group(1)):
                return m.group(1)
    return None


def rewrite_versions(text: str, want: str) -> str:
    a, b, c = want.split(".")
    text = re.sub(r"(\b(?:filevers|prodvers)\s*=\s*)\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)",
                  rf"\g<1>({a}, {b}, {c}, 0)", text)
    return re.sub(r"(StringStruct\('(?:FileVersion|ProductVersion)',\s*')\d+(?:\.\d+)*(')",
                  rf"\g<1>{want}\g<2>", text)


def sync_pyproject(want: str) -> list[str]:
    touched = []
    for p in (Path("pyproject.toml"), Path("pegasus/pyproject.toml")):
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        new, n = re.subn(r'(?m)^version\s*=\s*"[^"]+"', f'version = "{want}"', text)
        if n and new != text:
            p.write_text(new, encoding="utf-8", newline="\n")
            touched.append(str(p))
    return touched


def sync_package_json(want: str) -> bool:
    p = Path("pegasus/ui/web/package.json")
    if not p.exists():
        return False
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("version") == want:
        return False
    data["version"] = want
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    return True


def consolidate_version() -> None:
    say("7/21 version single-source")
    want = canonical_version()
    if want is None:
        say("    no version found anywhere — skipping")
        return
    sources = [r for r in PYRESOURCES if Path(r).exists()]
    say(f"    canonical {want}")
    for rel in sources:
        got = extract_version(Path(rel).read_text(encoding="utf-8", errors="replace"))
        print(f"      {rel}: {got} — {'agrees' if got == want else 'stale'}")
    write(str(VERSION_FILE), want + "\n")
    for p in sync_pyproject(want):
        print(f"    synced {p}")
    if sync_package_json(want):
        print("    synced pegasus/ui/web/package.json")
    if not sources:
        say("    no root version resources to retire")
        return
    if not (Path("pyproject.toml").exists() or Path("pegasus/pyproject.toml").exists()):
        say("    pyproject absent — keeping root resources")
        return
    RESOURCE_DEST.mkdir(parents=True, exist_ok=True)
    rows = []
    for rel in sources:
        body = rewrite_versions(Path(rel).read_text(encoding="utf-8", errors="replace"), want)
        dest = RESOURCE_DEST / rel
        dest.write_text(body, encoding="utf-8", newline="\n")
        git_remove(rel)
        Path(rel).unlink(missing_ok=True)
        rows.append(f"| `{rel}` | -> `{dest}` | rewritten to {want} |")
    write("archive/root-entrypoints/VERSION.md",
          "# Version consolidation\n\n" f"Canonical: `{want}` in `pegasus/VERSION`.\n\n"
          "| From | To | Note |\n|---|---|---|\n" + "\n".join(rows) + "\n")


def strip_block(text: str) -> str:
    keep, inside = [], False
    for line in text.splitlines(keepends=True):
        if line.startswith(MANAGED_BEGIN):
            inside = True
            continue
        if line.startswith(MANAGED_END):
            inside = False
            continue
        if not inside:
            keep.append(line)
    return "".join(keep)


def strip_rule(text: str, name: str) -> tuple[str, bool]:
    lines, out, i, removed = text.splitlines(keepends=True), [], 0, False
    while i < len(lines):
        if lines[i].rstrip("\n") == f"{name}:":
            removed = True
            i += 1
            while i < len(lines) and (lines[i].startswith("\t") or
                                      lines[i].startswith("    ")):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "".join(out), removed


def plan_makefile(text: str) -> tuple[str, list[str]]:
    text = strip_block(text)
    stripped = []
    for name in MANAGED_TARGETS:
        text, removed = strip_rule(text, name)
        if removed:
            stripped.append(name)
    body = text.rstrip("\n")
    body = body + "\n\n" if body else ""
    return body + MANAGED_BEGIN + MAKEFILE_BLOCK + MANAGED_END + "\n", stripped


def reconcile_makefile() -> None:
    say("8/21 Makefile")
    mk = Path("Makefile")
    original = mk.read_text(encoding="utf-8") if mk.exists() else ""
    if original:
        backup = Path("build/.tooling-backup") / stamp()
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mk, backup / "Makefile")
    new, stripped = plan_makefile(original)
    say(f"    reconciled {len(stripped)} rule(s)" if stripped else "    no conflicts")
    mk.write_text(new, encoding="utf-8", newline="\n")


def prune(backup_root: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for rel, verdict, reason in PRUNE:
        path = Path(rel)
        if not path.exists():
            rows.append((rel, "SKIP", "absent"))
            continue
        dst = backup_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(path, dst)
        if verdict == "MOVE":
            target = Path(MOVE_DEST[rel])
            if target.exists():
                rows.append((rel, "SKIP", f"destination exists: {target}"))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            git_remove(rel)
            path.unlink(missing_ok=True)
            rows.append((rel, "MOVE", f"-> {target}; {reason}"))
            continue
        git_remove(rel)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        rows.append((rel, verdict, reason))
    return rows


def run_prune() -> None:
    say("9/21 prune or regenerate unwired root files")
    backup_root = Path("build/.prune-backup") / stamp()
    rows = prune(backup_root)
    done = [r for r in rows if r[1] != "SKIP"]
    if not done:
        say("    nothing to handle")
        return
    lines = ["# Root entrypoint diff", "",
             f"Reversible from `{backup_root.as_posix()}` or from git.", "",
             "| Path | Verdict | Reason |", "|---|---|---|"]
    lines += [f"| `{p}` | {v} | {r} |" for p, v, r in rows]
    write("archive/root-entrypoints/DIFF.md", "\n".join(lines) + "\n")
    for path, verdict, reason in done:
        print(f"    {verdict:<10} {path} — {reason}")
    say(f"    {len(done)} path(s) handled")


def write_all() -> None:
    say("1/21 directories")
    for rel in ("docs/api", "docs/adr", "docs/templates", "build", "scripts", "skills",
                "assets/icons", "archive/root-entrypoints", ".githooks",
                "core", "transports", "risk", "builds", "truth", "audit",
                "investigate", "report", "discovery", "planning", "evals",
                "ai/backends", "delivery/vectors",
                "post_exploitation/manifests",
                "pegasus/harness", "pegasus/risk/register", "pegasus/tests/unit",
                "pegasus/tests/integ", "pegasus/tests/contract", "pegasus/tests/fixture",
                "pegasus/tests/py", "pegasus/tests/conformance",
                "pegasus/tests/transcripts", "pegasus/tests/eval"):
        Path(rel).mkdir(parents=True, exist_ok=True)

    diff = Path("build/map.diff")
    if not diff.exists():
        write("build/map.diff",
              "# path<TAB>verdict<TAB>reason — verdicts: KEEP MOVE MERGE DELETE "
              "ARCHIVE VENDOR GENERATE\n"
              "UNKNOWN\tUNKNOWN\tnot yet assigned\n")

    say("2/21 tooling")
    for rel, body in PAYLOADS.items():
        write(rel, body, executable=rel.startswith("scripts/"))

    say("3/21 capability scaffold")
    for rel, body in SPECS.items():
        write(rel, body)

    say("4/21 skills")
    write("skills/SKILL.md", SKILL_MD)
    for name, body in SKILLS.items():
        write(f"skills/{name}", body)
    write("skills/agents.yaml", AGENTS_YAML)

    say("5/21 phase contract")
    write("build/phases.yaml", PHASES_YAML)

    say("6/21 hooks")
    write(".githooks/pre-commit", PRE_COMMIT, executable=True)
    write(".githooks/pre-push", PRE_PUSH, executable=True)
    write(".githooks/commit-msg", COMMIT_MSG, executable=True)

    say("6b/21 hooksPath")
    run(["git", "config", "core.hooksPath", ".githooks"], check=True)


def sequence() -> int:
    say("10/21 checksums")
    STATE.write_text(
        "".join(f"{sha256(Path(rel))} {rel}\n" for rel in TOOLING), encoding="utf-8")
    say("11/21 plan-lint")
    run([sys.executable, "scripts/require.py", "--lint"], check=True)
    say("12/21 handoff")
    run([sys.executable, "scripts/handoff.py"], check=True)
    run([sys.executable, "scripts/handoff.py", "--check"], check=True)
    say("13/21 adapters")
    run([sys.executable, "scripts/emit_agents.py"], check=True)
    run([sys.executable, "scripts/emit_agents.py", "--check"], check=True)
    say("14/21 tamper check")
    run([sys.executable, "scripts/bootstrap-check.py"], check=True)
    say("15/21 version check")
    run([sys.executable, "scripts/version_check.py"], check=True)
    say("16/21 spec lints")
    run([sys.executable, "scripts/modules_lint.py"], check=True)
    run([sys.executable, "scripts/risk_lint.py"], check=True)
    say("17/21 capability matrix")
    run([sys.executable, "scripts/caps_matrix.py"], check=True)
    run([sys.executable, "scripts/caps_consistency.py"], check=True)
    say("18/21 compile")
    compiled = 0
    for rel in (*PAYLOADS, *SPEC_PY):
        run([sys.executable, "-m", "py_compile", rel], check=True)
        compiled += 1
    print(f"    {compiled} payloads compile")
    say("19/21 derived audit")
    run([sys.executable, "scripts/audit_derive.py"], check=True)
    run([sys.executable, "scripts/audit_derive.py", "--check"], check=True)
    say("20/21 target audit")
    mk = Path("Makefile").read_text(encoding="utf-8")
    absent = [t for t in MANAGED_TARGETS if f"\n{t}:" not in mk]
    if absent:
        die(f"managed targets missing after reconcile: {absent}")
    print(f"    {len(MANAGED_TARGETS)} targets present")
    say("21/21 adapter audit")
    for tool in ("opencode", "mimocode", "zcode", "openfable", "zfable"):
        for name in ("skill.json", "pegasus-gates.json"):
            if not Path(f".{tool}-skills/{name}").exists():
                die(f"adapter missing: .{tool}-skills/{name} "
                    f"(restore from build/.prune-backup)")
    print("    5/5 tools have both manifests")
    return 0


def self_test() -> int:
    say("self-test")
    fails = 0

    def check(name: str, cond: bool) -> None:
        nonlocal fails
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        fails += 0 if cond else 1

    # -- capreg parses values, by AST, and survives reformatting
    with tempfile.TemporaryDirectory() as td:
        caps = Path(td) / "caps.py"
        caps.write_text('"""docstring."""\nfrom enum import Enum\n\n\n'
                        'class Cap(str, Enum):\n'
                        '    # a comment inside the enum\n'
                        '    SHELL = "shell"\n'
                        '    FILE_GET = "file.get"\n', encoding="utf-8")
        (Path(td) / "scripts").mkdir()
        (Path(td) / "scripts/capreg.py").write_text(
            PAYLOADS["scripts/capreg.py"], encoding="utf-8")
        out = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'%s');"
             "import capreg;"
             "print(','.join(capreg.cap_values(__import__('pathlib').Path(r'%s'))))"
             % ((Path(td) / "scripts").resolve(), caps)],
            capture_output=True, text=True, cwd=td)
        check("capreg parses values not names",
              out.returncode == 0 and out.stdout.strip() == "shell,file.get")
        caps.write_text('class Cap(str, Enum):\n    SHELL="shell"\n', encoding="utf-8")
        out2 = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'%s');"
             "import capreg;"
             "print(','.join(capreg.cap_values(__import__('pathlib').Path(r'%s'))))"
             % ((Path(td) / "scripts").resolve(), caps)],
            capture_output=True, text=True, cwd=td)
        check("capreg survives reformatting", out2.stdout.strip() == "shell")
        caps.write_text('class Other:\n    X = 1\n', encoding="utf-8")
        out3 = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'%s');"
             "import capreg;"
             "capreg.cap_values(__import__('pathlib').Path(r'%s'))"
             % ((Path(td) / "scripts").resolve(), caps)],
            capture_output=True, text=True, cwd=td)
        check("capreg raises on a missing enum",
              out3.returncode == 1 and "no class Cap" in out3.stderr)

    # -- every register proof has a seeded stub, and no stub is orphaned
    declared = {line.split("proof:", 1)[1].split(",")[0].strip()
                for line in RISK_REGISTER.splitlines() if "proof:" in line}
    seeded = set(PROOFS)
    check("every risk proof is seeded", declared == seeded)
    check("no orphan proof stub", seeded == {p for p, _, _ in _PROOF_SPECS})

    # -- reconcile: strips what it owns, keeps what it does not, idempotent
    fixture = ("install:\n\tpip install -e .\n\napply:\n\tpython x.py\n\n"
               "test:\n\tpytest -q\n\nverify:\n\tpython scripts/verify.py\n\n"
               "smoke:\n\tbash s.sh\n")
    out, stripped = plan_makefile(fixture)
    check("strips repo test rule", "test:\n\tpytest -q" not in out)
    check("strips repo verify rule", "verify:\n\tpython scripts/verify.py\n" not in out)
    check("keeps install",
          out.startswith("install:") or "\ninstall:" in out)
    check("keeps apply", "\napply:" in out)
    check("keeps smoke", "\nsmoke:" in out)
    check("adds managed block", MANAGED_BEGIN in out and MANAGED_END in out)
    check("block defines audit", "\naudit:" in out)
    check("block defines require", "\nrequire:" in out)
    check("block defines map", "\nmap:" in out)
    check("block defines caps-consistency", "\ncaps-consistency:" in out)
    check("records what it stripped", set(stripped) == {"test", "verify"})
    out2, stripped2 = plan_makefile(out)
    check("idempotent: one block", out2.count(MANAGED_BEGIN) == 1)
    check("idempotent: stable", out2 == out)
    check("second pass strips nothing", stripped2 == [])
    empty, _ = plan_makefile("")
    check("empty Makefile still yields a block", "\nrequire:" in empty)
    check("empty Makefile has no leading blank", not empty.startswith("\n"))

    # -- version rewrite
    vres = "filevers=(1, 4, 0, 0),\nStringStruct('FileVersion', '1.4.0')"
    check("extracts version", extract_version(vres) == "1.4.0")
    check("rewrites tuple", "(2, 1, 0, 0)" in rewrite_versions(vres, "2.1.0"))
    check("rewrites string", "'2.1.0'" in rewrite_versions(vres, "2.1.0"))
    check("no stale tuple", "(1, 4, 0, 0)" not in rewrite_versions(vres, "2.1.0"))
    check("higher version wins",
          max(["1.4.0", "2.1.0"], key=lambda v: tuple(int(x) for x in v.split(".")))
          == "2.1.0")

    # -- payloads and scaffold both compile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for rel, body in {**PAYLOADS, **SPECS}.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        for rel in (*PAYLOADS, *SPEC_PY):
            code = subprocess.run([sys.executable, "-m", "py_compile", str(root / rel)],
                                  capture_output=True, text=True)
            check(f"compiles {rel}", code.returncode == 0)
            if code.returncode:
                print("      " + code.stderr.strip().splitlines()[-1])

        (root / "tests").mkdir(exist_ok=True)

        def lint(script: str) -> tuple[int, str]:
            proc = subprocess.run([sys.executable, str(root / script)],
                                  capture_output=True, text=True, cwd=root)
            return proc.returncode, proc.stdout + proc.stderr

        # -- lints pass on the seeds
        check("modules_lint passes on seeds", lint("scripts/modules_lint.py")[0] == 0)
        check("risk_lint passes on seeds", lint("scripts/risk_lint.py")[0] == 0)
        check("caps_matrix passes on seeds", lint("scripts/caps_matrix.py")[0] == 0)
        check("caps_consistency passes on seeds",
              lint("scripts/caps_consistency.py")[0] == 0)

        # -- matrix emits machine-readable output alongside prose
        (root / "build").mkdir(exist_ok=True)
        lint("scripts/caps_matrix.py")
        js = root / "build/caps_matrix.json"
        check("matrix writes json", js.exists())
        check("json carries a verdict",
              js.exists() and '"status": "PASS"' in js.read_text(encoding="utf-8"))
        check("json lists every cap",
              js.exists() and '"shell"' in js.read_text(encoding="utf-8"))

        # -- an orphan cap fails BOTH lints, and the consistency check agrees
        cm = root / "core/caps.py"
        cm.write_text('class Cap(str, Enum):\n'
                      '    SHELL = "shell"\n'
                      '    FAKE = "fake.cap"\n', encoding="utf-8")
        (root / "transports/registry.yaml").write_text(
            "- {name: adb, cost: 10, provides: [shell]}\n", encoding="utf-8")
        # isolate the enum: seed manifests reference caps this one transport does
        # not provide, and would otherwise mask the orphan under test
        for seed_mf in (root / "post_exploitation/manifests").glob("*.yaml"):
            seed_mf.unlink()
        a, a_out = lint("scripts/modules_lint.py")
        b, b_out = lint("scripts/caps_matrix.py")
        check("modules_lint fails on an orphan", a == 2 and "orphan cap" in a_out)
        check("caps_matrix fails on an orphan", b == 2 and "fake.cap" in b_out)
        c, c_out = lint("scripts/caps_consistency.py")
        check("consistency agrees when both fail", c == 2 and "both lints agree" in c_out)

        # -- waiving the orphan clears both, and reports the waiver
        (root / "build/caps_orphans.allow").write_text(
            "fake.cap   # adapter not written yet\n", encoding="utf-8")
        check("waiver clears modules_lint", lint("scripts/modules_lint.py")[0] == 0)
        d, d_out = lint("scripts/caps_matrix.py")
        check("waiver clears caps_matrix", d == 0)
        check("waiver is reported not hidden", "waived" in d_out)

        # -- a phantom provides entry fails both
        (root / "build/caps_orphans.allow").write_text("", encoding="utf-8")
        (root / "transports/registry.yaml").write_text(
            "- {name: adb, cost: 10, provides: [shell, typo.cap]}\n", encoding="utf-8")
        e, e_out = lint("scripts/modules_lint.py")
        f, f_out = lint("scripts/caps_matrix.py")
        check("modules_lint fails on a phantom", e == 2 and "phantom" in e_out)
        check("caps_matrix fails on a phantom", f == 2 and "typo.cap" in f_out)

        # -- a real disagreement is exit 3, not 2
        broken = root / "scripts/caps_matrix.py"
        original = broken.read_text(encoding="utf-8")
        broken.write_text(original.replace("return 2 if failed else 0", "return 0"),
                          encoding="utf-8")
        g, g_out = lint("scripts/caps_consistency.py")
        check("consistency catches disagreement", g == 3 and "DISAGREEMENT" in g_out)
        broken.write_text(original, encoding="utf-8")

        # -- remaining lints fire on their own fixtures
        mf = root / "post_exploitation/manifests/09_broken.yaml"
        mf.write_text("- id: bad_dep\n  title: x\n  category: x\n  tier: 3\n"
                      "  requires_caps: {all: [shell]}\n  depends_on: [nope]\n",
                      encoding="utf-8")
        check("modules_lint catches bad dep", lint("scripts/modules_lint.py")[0] == 2)
        mf.write_text("- id: bad_cap\n  title: x\n  category: x\n  tier: 3\n"
                      "  requires_caps: {all: [not.a.cap]}\n", encoding="utf-8")
        check("modules_lint catches bad cap", lint("scripts/modules_lint.py")[0] == 2)
        mf.write_text("- id: a1\n  title: x\n  category: x\n  tier: 3\n"
                      "  requires_caps: {all: [shell]}\n  depends_on: [b1]\n"
                      "- id: b1\n  title: y\n  category: x\n  tier: 3\n"
                      "  requires_caps: {all: [shell]}\n  depends_on: [a1]\n",
                      encoding="utf-8")
        check("modules_lint catches cycle", lint("scripts/modules_lint.py")[0] == 2)
        mf.unlink()

        rr = root / "risk/register.yaml"
        rr.write_text("- {id: R-X-01, title: t, area: device, severity: high,"
                      " detector: d, owner: o, sla_hours: 1}\n", encoding="utf-8")
        check("risk_lint catches missing proof", lint("scripts/risk_lint.py")[0] == 2)
        rr.write_text("- {id: R-X-01, title: t, area: device, severity: high,"
                      " detector: d, ladder: [a], auto: [b], proof: tests/nope.py,"
                      " owner: o, sla_hours: 1}\n", encoding="utf-8")
        check("risk_lint catches missing proof file", lint("scripts/risk_lint.py")[0] == 2)

        mod = root / "pegasus/modules/x"
        mod.mkdir(parents=True)
        (mod / "module.py").write_text("def f(h):\n    if platform == 'android':\n"
                                       "        return 1\n", encoding="utf-8")
        check("noplatform catches a branch",
              lint("scripts/no_platform_branch.py")[0] == 2)
        (mod / "module.py").write_text("def f(h):\n    return 1\n", encoding="utf-8")
        check("noplatform passes clean module",
              lint("scripts/no_platform_branch.py")[0] == 0)

        web = root / "pegasus/ui/web/src"
        web.mkdir(parents=True)
        (web / "Nav.tsx").write_text("export const n = 'Dashboard';\n", encoding="utf-8")
        check("capability_check catches old label",
              lint("scripts/capability_check.py")[0] == 2)
        (web / "Nav.tsx").write_text("export const n = 'Capability';\n", encoding="utf-8")
        check("capability_check passes after rename",
              lint("scripts/capability_check.py")[0] == 0)

        check("audit derives without crashing", lint("scripts/audit_derive.py")[0] == 0)
        check("audit --check passes after derive",
              subprocess.run([sys.executable, str(root / "scripts/audit_derive.py"),
                              "--check"], capture_output=True, cwd=root).returncode == 0)

    check("managed targets cover every gate target",
          all(t in MANAGED_TARGETS for t in
              ("setup", "test", "contract", "conformance", "modules-lint",
               "audit-check", "map", "capability-check", "noplatform", "risk-lint",
               "caps-matrix", "caps-consistency")))
    check("all payloads registered as tooling",
          all(rel in TOOLING for rel in PAYLOADS
              if rel != "pegasus/tests/contract/test_agents.py"))
    check("no spec payload collides with a tooling path",
          not (set(SPECS) & set(TOOLING)))
    check("every scaffold py file is registered for compilation",
          all(rel in SPECS for rel in SPEC_PY))
    check("capreg is tooling, not scaffold",
          "scripts/capreg.py" in TOOLING and "scripts/capreg.py" not in SPECS)

    print(f"\n{'PASS' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pegasus bootstrap")
    parser.add_argument("--force", action="store_true",
                        help="overwrite locally modified tooling (backs up first)")
    parser.add_argument("--no-prune", action="store_true", help="leave root files in place")
    parser.add_argument("--self-test", action="store_true",
                        help="exercise every lint, capreg and the reconcile, then exit")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if not Path(".git").is_dir():
        die("run from the repo root (no .git here)")
    if not Path("docs/PLAN.md").exists():
        die("docs/PLAN.md missing — save the plan there first")

    ensure_pyyaml()
    check_drift(args.force)
    write_all()
    consolidate_version()
    reconcile_makefile()
    if not args.no_prune:
        run_prune()
    if sequence() != 0:
        die("sequence failed — see output above")

    say("done")
    print(
        "\nNext:\n"
        "  git checkout -b P0/plan-and-handoff\n"
        "  git add -A\n"
        '  git commit -m "P0: land plan, tooling, hooks, adapters and scaffold"\n'
        "  python scripts/require.py P1\n\n"
        "The audit reads 0% on purpose: every seeded module is T3 until P11\n"
        "writes its body and fixture. `make audit` prints the derived split.\n\n"
        "Expected red on day one, all correct:\n"
        "  make map             G11, seeded UNKNOWN row printed\n"
        "  make capability-check  nav still says Dashboard (P6)\n"
        "  make noplatform      no module.py yet, exit 3 (P11)\n"
        "  make conformance/replay/evidence-check/eval  empty dirs, exit 5\n\n"
        "Cap lints share scripts/capreg.py. To add a module needing an unprovided\n"
        "cap: make caps-matrix, read build/caps_matrix.json, then either wire a\n"
        "transport or add the cap to build/caps_orphans.allow with a reason.\n"
        "make caps-consistency exits 3 if the two lints ever disagree.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())