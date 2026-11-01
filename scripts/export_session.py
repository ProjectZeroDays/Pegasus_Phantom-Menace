"""Zip a run for handoff. Optional encryption."""
import argparse
import json
import pathlib
import zipfile

from pegasus.modules.autonomous import journal
from pegasus.modules.crypto import atrest


def main(run_id: str, out: pathlib.Path, encrypt: bool) -> None:
    run = pathlib.Path.home() / ".pegasus" / "runs" / run_id
    if not run.exists():
        raise SystemExit(f"no run {run_id}")
    events = journal.replay(run_id)
    if encrypt:
        payload = {"journal": events,
                   "loot": {p.name: p.read_text(errors="ignore")
                            for p in (run / "loot").rglob("*") if p.is_file()}}
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("session.enc", atrest.seal(payload))
    else:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("journal.json", json.dumps(events, indent=2))
            for path in (run / "loot").rglob("*"):
                if path.is_file():
                    zf.write(path, f"loot/{path.relative_to(run / 'loot')}")
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("-o", "--out", type=pathlib.Path, required=True)
    ap.add_argument("--encrypt", action="store_true")
    args = ap.parse_args()
    main(args.run_id, args.out, args.encrypt)
