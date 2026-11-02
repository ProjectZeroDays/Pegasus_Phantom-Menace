#!/usr/bin/env python3
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
