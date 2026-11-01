"""LoRA + DPO. Writes a candidate adapter, never touches the base."""
import json
import pathlib
import subprocess
import sys
import time

from . import preferences, traces

WORK = pathlib.Path.home() / ".pegasus" / "training"


class Insufficient(RuntimeError):
    pass


def _jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows))


def run(role: str, base: str) -> pathlib.Path:
    sft = traces.accepted(role)
    if len(sft) < traces.MIN_SFT:
        raise Insufficient(f"{len(sft)} rows, need {traces.MIN_SFT}")
    work = WORK / f"{role}-{int(time.time())}"
    work.mkdir(parents=True, exist_ok=True)
    _jsonl(work / "sft.jsonl", sft)
    if dp := preferences.pairs(role):
        _jsonl(work / "dpo.jsonl", dp)
    if sys.platform == "darwin":
        subprocess.run(["python", "-m", "mlx_lm.lora", "--model", base,
                        "--train", "--data", str(work), "--iters", "600"], check=True)
    else:
        subprocess.run(["python", "-m", "unsloth.train", str(work), base], check=True)
    (work / "META.json").write_text(json.dumps({"role": role, "base": base,
                                                "rows": len(sft)}))
    return work
