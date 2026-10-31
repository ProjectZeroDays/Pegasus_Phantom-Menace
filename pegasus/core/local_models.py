#!/usr/bin/env python3
"""Local AI model manager for Pegasus v2.1 — GGUF / MLX / abliterated."""
from __future__ import annotations
import os, sys, platform, json, pathlib
from typing import List, Dict, Optional

MODELS_DIR = pathlib.Path(os.getenv("PEGASUS__WORKSPACE", ".")).expanduser() / ".pegasus" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

HW = {
    "system": platform.system().lower(),
    "machine": platform.machine(),
    "processor": platform.processor(),
}

def best_formats() -> List[str]:
    s = HW["system"]
    if s in ("darwin",) or HW["machine"].startswith("arm"):
        return ["mlx"]
    return ["gguf"]

def recommended_models() -> List[Dict]:
    fmt_order = best_formats()
    return [
        {"id": "claude-sonnet-4-6", "label": "claude-sonnet-4-6 (best)", "formats": fmt_order, "size_gb": 8},
        {"id": "llama-3.1-70b-q4", "label": "llama-3.1-70b-q4 (win/linux gguf)", "formats": ["gguf"], "size_gb": 40},
        {"id": "qwen-2.5-32b-q4", "label": "qwen-2.5-32b-q4 (mac mlx)", "formats": ["mlx"], "size_gb": 18},
    ]

def download(model_id: str) -> Dict[str, str]:
    return {"status": "queued", "model": model_id, "dir": str(MODELS_DIR), "message": "Download queued to workspace/models/"}

def list_local() -> List[str]:
    return [str(p.name) for p in MODELS_DIR.glob("*.gguf") + list(MODELS_DIR.glob("*.mlx"))]
