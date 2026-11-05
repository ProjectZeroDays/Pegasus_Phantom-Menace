#!/usr/bin/env python3
"""Second repair: layout-independent secret-key fix, then finish the series."""
from __future__ import annotations

import subprocess
import sys

import apply_lib as L
import apply_repair as R

SECRET_BLOCK = '''    secret_file = pathlib.Path.home().joinpath(".pegasus", ".secret")
    if not secret_file.exists():
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        import secrets
        secret_file.write_text(secrets.token_hex(32), encoding="utf-8")
        try:
            secret_file.chmod(0o600)
        except OSError:
            pass
    app.secret_key = secret_file.read_text(encoding="utf-8").strip()'''


def fix_secret() -> int:
    print("A2 secret key (regex, layout independent)")
    text = R.APP.read_text(encoding="utf-8")
    if "secret_file =" in text:
        print("  skip  already applied")
        return 0

    lines = text.split("\n")
    start = None
    for index, line in enumerate(lines):
        if "app.secret_key" in line:
            start = index
            break
    if start is None:
        print("  FAIL  no line contains 'app.secret_key'")
        print("  app.py head:")
        for line in lines[:20]:
            print(f"    {line}")
        return 2

    end = start
    while end + 1 < len(lines) and lines[end + 1].strip() and lines[end + 1][:1] in (" ", "\t"):
        end += 1

    print(f"  replacing lines {start + 1}-{end + 1}")
    for line in lines[start:end + 1]:
        print(f"    - {line}")
    lines[start:end + 1] = SECRET_BLOCK.split("\n")
    R.APP.write_text("\n".join(lines), encoding="utf-8")
    print("  ok    app.py :: persist secret once")
    return 0


def main() -> int:
    if not (L.WEB / "src" / "pages").is_dir():
        print("run from the repo root"); return 1

    code = R.clean()
    if code:
        return code

    code = fix_secret()
    if code:
        return code

    R.EDITS = [e for e in R.EDITS if e[0] != R.APP]
    print("B  remaining edits")
    code = R.apply_edits()
    if code:
        return code

    if subprocess.call([sys.executable, "-m", "py_compile", str(R.APP)]) != 0:
        print("  app.py compile failed")
        return 3
    print("  app.py compiles")

    L.phase_c()

    print("E  typecheck")
    if subprocess.call("npx tsc --noEmit", cwd=str(L.WEB), shell=True) != 0:
        print("  tsc failed — not committing")
        return 4
    print("  tsc clean")

    L.phase_d()

    if "--no-commit" in sys.argv:
        print("\n--no-commit set"); return 0

    subprocess.call("git add -A", cwd=str(R.ROOT), shell=True)
    subprocess.call(
        'git commit -m "web: restore src/lib, add device routes, apply fix series, scaffold fable" '
        '-m "Sweeps 5.1 5.3 7.1 7.2 8.1 8.2 8.3 10.1 12.3."',
        cwd=str(R.ROOT), shell=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())