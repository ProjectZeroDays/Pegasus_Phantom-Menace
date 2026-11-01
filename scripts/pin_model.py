"""Resolve a repo+quant to a pinned file. LFS oid is the content sha256."""
import argparse
import pathlib

import requests

TREE = "https://huggingface.co/api/models/{repo}/tree/main"
CARD = "https://huggingface.co/api/models/{repo}"


def resolve(repo: str, quant: str) -> dict:
    meta = requests.get(CARD.format(repo=repo), timeout=20).json()
    licence = (meta.get("cardData") or {}).get("license") or "unknown"
    for entry in requests.get(TREE.format(repo=repo), timeout=20).json():
        name = entry.get("path", "")
        if quant != "mlx" and (not name.lower().endswith(".gguf")
                               or quant.lower() not in name.lower()):
            continue
        oid = (entry.get("lfs") or {}).get("oid")
        if not oid:
            raise SystemExit(f"{name}: not LFS, cannot pin by hash")
        return {"url": f"https://huggingface.co/{repo}/resolve/main/{name}",
                "sha256": oid, "size": entry.get("size", 0), "licence": licence}
    raise SystemExit(f"{repo}: no file matching {quant}")


def main(repo: str, quant: str, out: str) -> None:
    pin = resolve(repo, quant)
    path = pathlib.Path(out)
    text = path.read_text() if path.exists() else "PINS: dict = {}\n"
    if pin["sha256"] in text:
        print("already pinned")
        return
    line = (f'PINS[("{repo}", "{quant}")] = Pin("{pin["url"]}", "{pin["sha256"]}", '
            f'{pin["size"]}, "{pin["licence"]}")\n')
    path.write_text(text + line)
    print(line, end="")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("quant", nargs="?", default="Q4_K_M")
    ap.add_argument("--out", default="pegasus/modules/ai/pins_data.py")
    args = ap.parse_args()
    main(args.repo, args.quant, args.out)
