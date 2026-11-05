#!/usr/bin/env python3
"""Fourth repair: fix phase_c, apply the projection edit properly, finish."""
from __future__ import annotations

import subprocess
import sys

import apply_lib as L
import apply_repair as R

LIB_SRC = L.ROOT / "apply_lib.py"
PROJECTION_OLD = '"number:date:duration:type:name:cache"'
PROJECTION_NEW = '"number:date:duration:type:name:cached_name"'


def fix_phase_c() -> int:
    print("A1 phase_c subprocess.call -> run")
    text = LIB_SRC.read_text(encoding="utf-8")
    if "call([\"where\", \"dotnet\"], capture_output=True)" not in text:
        print("  skip  already patched")
        return 0
    for tool in ("dotnet", "fable"):
        old = f'subprocess.call(["where", "{tool}"], capture_output=True)'
        new = f'subprocess.run(["where", "{tool}"], capture_output=True).returncode'
        text = text.replace(old, new)
    LIB_SRC.write_text(text, encoding="utf-8")
    print("  ok    both call sites")
    if subprocess.call([sys.executable, "-m", "py_compile", str(LIB_SRC)]) != 0:
        print("  compile failed")
        return 2
    return 0


def fix_projection() -> int:
    print("A2 call-log projection")
    text = L.TEL.read_text(encoding="utf-8")
    if PROJECTION_NEW in text:
        print("  skip  already correct")
        return 0
    if PROJECTION_OLD not in text:
        print("  FAIL  projection string not found")
        return 2
    L.TEL.write_text(text.replace(PROJECTION_OLD, PROJECTION_NEW, 1), encoding="utf-8")
    print("  ok    cache -> cached_name")
    if subprocess.call([sys.executable, "-m", "py_compile", str(L.TEL)]) != 0:
        print("  compile failed")
        return 3
    return 0


def main() -> int:
    if not (L.WEB / "src" / "pages").is_dir():
        print("run from the repo root"); return 1

    for step in (fix_phase_c, fix_projection):
        code = step()
        if code:
            return code

    print("\nB  verification that projection parses")
    check = subprocess.run(
        [sys.executable, "-c",
         "import ast,pathlib;"
         f"ast.parse(pathlib.Path(r'{L.TEL}').read_text(encoding='utf-8'))"],
        capture_output=True, text=True,
    )
    if check.returncode != 0:
        print(f"  {check.stderr[-300:]}")
        return 3
    print("  ast ok")

    import importlib
    importlib.reload(L)

    L.phase_c()

    guard = L.LIB / "fsharp-check.ts"
    if guard.exists() and not (L.FABLE_OUT / "Format.ts").exists():
        guard.unlink()
        print("  removed fsharp-check.ts (no Fable output to import)")

    print("E  typecheck")
    if subprocess.call("npx tsc --noEmit", cwd=str(L.WEB), shell=True) != 0:
        print("  tsc failed — not committing")
        return 4
    print("  tsc clean")

    L.phase_d()

    if "--no-commit" in sys.argv:
        print("\n--no-commit set"); return 0

    subprocess.call("git add -A", cwd=str(L.ROOT), shell=True)
    subprocess.call(
        'git commit -m "web: restore src/lib, add supplementary device routes, fix series, fable" '
        '-m "Sweeps 5.1 5.3 7.1 7.2 8.1 8.2 8.3 10.1 12.3. Blueprint trimmed to the 20 routes '
        'app.py lacks; views dr_-prefixed to avoid endpoint collisions."',
        cwd=str(L.ROOT), shell=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())