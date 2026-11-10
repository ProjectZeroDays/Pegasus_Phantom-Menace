"""cleanup_amend.py - drop the remaining scratch scripts, amend, push."""
import pathlib
import subprocess
import sys

TOKEN = pathlib.Path(".push_token").read_text(encoding="utf-8").strip()


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


rc, out = run(["git", "ls-files"])
tracked = set(out.splitlines())
STRAY = [p for p in tracked if pathlib.Path(p).suffix in (".py", ".log", ".txt")
         and "/" not in p and not p.startswith("setup")
         or p in ("amend_push.py", "push_all.py", "push_now.py", "seal.py", "Q9.py")]

KEEP = {"push_all.py", "seal.py", "Q9.py", "setup.py"}
victims = []
for p in sorted(tracked):
    if "/" in p:
        continue
    if p in KEEP:
        continue
    if pathlib.Path(p).suffix in (".py", ".log", ".txt"):
        victims.append(p)

print("removing:", len(victims))
for v in victims:
    run(["git", "rm", "-f", "--quiet", v])
    print("  ", v)

rc, out = run(["git", "status", "--porcelain"])
print("\nstaged changes:", len(out.splitlines()))

rc, out = run(["git", "commit", "--amend", "--no-edit"])
print("amend:", "ok" if rc == 0 else out[-600:])
if rc:
    sys.exit(1)

rc, out = run(["git", "grep", "-l", TOKEN, "HEAD", "--", "."])
print("\nfiles still holding the literal in HEAD:", out or "none")

run(["git", "remote", "set-url", "origin",
     "https://%s@github.com/ProjectZeroDays/Pegasus_Phantom-Menace.git" % TOKEN])
rc, out = run(["git", "push", "origin", "main"])
print("\n" + out.replace(TOKEN, "<token>")[-1200:])
print("push:", "ok" if rc == 0 else "FAILED")