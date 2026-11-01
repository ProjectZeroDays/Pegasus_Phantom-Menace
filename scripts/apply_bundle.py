"""Split a bundle file into real files. Refuses to overwrite without --force."""
import argparse
import pathlib
import re

MARK = re.compile(r"^=== FILE: (.+)$")
END = "=== END"


def parse(text: str) -> list[tuple[str, str]]:
    out, path, buf = [], None, []
    for line in text.splitlines():
        if MARK.match(line):
            path = MARK.match(line).group(1).strip()
            buf = []
        elif line.strip() == END and path:
            out.append((path, "\n".join(buf).rstrip() + "\n"))
            path = None
        elif path is not None:
            buf.append(line)
    return out


def main(bundle: pathlib.Path, root: pathlib.Path, force: bool) -> None:
    files = parse(bundle.read_text())
    written = skipped = 0
    for rel, body in files:
        target = root / rel
        if target.exists() and not force:
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
        written += 1
    print(f"{written} written, {skipped} skipped (use --force to overwrite)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=pathlib.Path)
    ap.add_argument("root", type=pathlib.Path, nargs="?", default=pathlib.Path("."))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    main(args.bundle, args.root, args.force)
