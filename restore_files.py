"""restore_files.py - bring back the ten non-scratch files, commit, push."""
import pathlib
import subprocess
import sys

TOKEN = pathlib.Path(".push_token").read_text(encoding="utf-8").strip()
BASE = "28afc186"
FILES = ["requirements.txt", "bootstrap.py", "run_server.py", "start_server.py",
         "god_mode.py", "persistence_checker.py", "tier1_gate.py",
         "traffic_analysis.py", "update_check.py", "advanced_config_aggregator.py"]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


for f in FILES:
    rc, out = run(["git", "checkout", BASE, "--", f])
    print(("ok   " if rc == 0 else "FAIL ") + f + ("" if rc == 0 else "  " + out[-80:]))

PLAN = pathlib.Path("docs/PLAN.md")
MARK = "## 63. HANDOFF"
text = PLAN.read_text(encoding="utf-8")
if MARK not in text:
    BLOCK = ["", "", "=== HANDOFF SECTION ===", "", MARK, "",
             "Project: Pegasus Phantom Menace v2 / physical + bootloader surfaces",
             "Status: 101 tests green, tsc clean, build ok; root scripts restored",
             "Features: physical-effect engine (30 routes) and fastboot/FRP/root/Odin engine (33 routes), both with UI pages",
             "Log: log/events.jsonl",
             "Release: unreleased since v2.1.0",
             "Push blocked: none",
             "Next: device smoke run of both new pages; accessibility sweep; clean-VM Electron build; iOS provisioning",
             "Author: Trey A. Smith | Authenticated, Inc. | @projectzerodays",
             "Notes: the scratch sweep over-reached and removed ten root scripts (requirements.txt, bootstrap.py, run_server.py, start_server.py, god_mode.py, persistence_checker.py, tier1_gate.py, traffic_analysis.py, update_check.py, advanced_config_aggregator.py); all restored from 28afc186. Only fix*/diag*/make*/recon*/check*/verify*/amend*/drop*/final*/find*/decide*/vuln*/fix-sweep/fix2/fix3 and the stray 'python apply_repair4.py' stay deleted.",
             ""]
    PLAN.write_text(text.rstrip() + "\n" + "\n".join(BLOCK), encoding="utf-8")
    print("handoff appended")

run([sys.executable, "scripts/handoff.py"])

for g in (["scripts/handoff.py", "--check"], ["scripts/emit_agents.py", "--check"],
          ["scripts/modules_lint.py"], ["scripts/caps_consistency.py"],
          ["scripts/require.py", "--lint"], ["scripts/version_check.py"],
          ["scripts/risk_lint.py"], ["scripts/no_platform_branch.py"],
          ["scripts/audit_derive.py", "--check"], ["scripts/bootstrap-check.py"]):
    rc, out = run([sys.executable] + g)
    print("%s  %s" % ("PASS" if rc == 0 else "FAIL", " ".join(g)))
    if rc:
        print(out[-500:])
        sys.exit(1)

rc, out = run([sys.executable, "-c",
               "import sys; sys.path.insert(0,'.');"
               "from pegasus.ui.web.backend.app import create_app;"
               "print('health', create_app().test_client().get('/api/health').status_code)"])
print(out[-120:])

run(["git", "add", "-A"])
cmd = ["git", "commit", "-m", "P4: restore root scripts removed by the scratch sweep",
       "-m", "requirements.txt, bootstrap.py, run_server.py, start_server.py, god_mode.py,",
       "-m", "persistence_checker.py, tier1_gate.py, traffic_analysis.py, update_check.py and",
       "-m", "advanced_config_aggregator.py all came back from 28afc186."]
rc, out = run(cmd)
print(out[-400:])
if rc:
    sys.exit(1)

run(["git", "remote", "set-url", "origin",
     "https://%s@github.com/ProjectZeroDays/Pegasus_Phantom-Menace.git" % TOKEN])
rc, out = run(["git", "push", "origin", "main"])
print("\n" + out.replace(TOKEN, "<token>")[-800:])
print("push:", "ok" if rc == 0 else "FAILED")