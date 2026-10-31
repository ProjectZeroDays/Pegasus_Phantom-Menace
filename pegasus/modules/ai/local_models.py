#!/usr/bin/env python3
"""Local AI model manager — GGUF / MLX, abliterated + quantized, gated by hardware."""
from __future__ import annotations
import json, os, platform, shutil, subprocess, sys, pathlib, threading
import requests

MODELS = pathlib.Path.home() / ".pegasus" / "models"
HF = "https://huggingface.co/api/models"
_LOCK = threading.Lock()
_RUNNING: dict = {}

def platform_tier() -> str:
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return "mlx"
    return "gguf"

def apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"

def total_ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().total / 1e9
    except Exception:
        return 8.0

def _budget_gb() -> float:
    return max(2.0, total_ram_gb() * 0.55)

def _quant_ok(name: str) -> str | None:
    n = name.lower()
    for q in ("q4_k_m", "q4_k_s", "q5_k_m", "q8_0", "q6_k"):
        if q in n:
            return q
    return None

def search(query: str = "abliterated", limit: int = 40) -> list[dict]:
    tier = platform_tier()
    params = {"search": query, "limit": limit, "sort": "downloads", "direction": -1}
    if tier == "gguf":
        params["filter"] = "gguf"
    r = requests.get(HF, params=params, timeout=20)
    r.raise_for_status()
    out = []
    for m in r.json():
        mid = m.get("modelId") or m.get("id") or ""
        if "abliterat" not in mid.lower():
            continue
        files = [s["rfilename"] for s in m.get("siblings", []) if s.get("rfilename")]
        if tier == "gguf":
            gguf = [f for f in files if f.lower().endswith(".gguf") and _quant_ok(f)]
            if not gguf:
                continue
            files = sorted(gguf, key=lambda f: ("q4_k_m" not in f.lower(), len(f)))[:3]
        out.append({"id": mid, "downloads": m.get("downloads", 0), "files": files, "tier": tier})
    return out

def recommended() -> list[dict]:
    budget = _budget_gb()
    ranked, missed = [], []
    for m in search():
        est = _estimate_gb(m["id"])
        item = dict(m); item["est_gb"] = round(est, 1); item["fits"] = est <= budget
        (ranked if item["fits"] else missed).append(item)
    ranked.sort(key=lambda m: (not m["fits"], -m["downloads"]))
    return ranked[:12]

def _estimate_gb(model_id: str) -> float:
    import re
    mm = re.search(r"(\d+(?:\.\d+)?)\s*b(?![a-z])", model_id.lower())
    params = float(mm.group(1)) if mm else 7.0
    return params * 0.62

def download(model_id: str, filename: str) -> pathlib.Path:
    MODELS.mkdir(parents=True, exist_ok=True)
    dest = MODELS / filename.split("/")[-1]
    if dest.exists():
        return dest
    url = f"https://huggingface.co/{model_id}/resolve/main/{filename}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    tmp.rename(dest)
    return dest

def installed() -> list[dict]:
    if not MODELS.exists(): return []
    return [{"file": p.name, "gb": round(p.stat().st_size / 1e9, 2)} for p in MODELS.glob("*.gguf")]

def installed_default() -> str | None:
    p = pathlib.Path.home() / ".pegasus" / "providers.json"
    data = json.loads(p.read_text()) if p.exists() else {}
    return data.get("localModel")

def serve(path: pathlib.Path, port: int = 8081) -> str:
    if _RUNNING.get("port"):
        return f"http://127.0.0.1:{_RUNNING['port']}/v1"
    with _LOCK:
        if _RUNNING.get("port"):
            return f"http://127.0.0.1:{_RUNNING['port']}/v1"
    if apple_silicon():
        cmd = [sys.executable, "-m", "mlx_lm.server", "--model", str(path), "--port", str(port)]
    else:
        binary = shutil.which("llama-server") or shutil.which("llama-server.exe")
        if not binary:
            raise RuntimeError("llama.cpp not found — install llama.cpp or `pip install llama-cpp-python[server]`")
        cmd = [binary, "-m", str(path), "-c", "8192", "--port", str(port), "--host", "127.0.0.1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _RUNNING.update(proc=proc, port=port)
    return f"http://127.0.0.1:{port}/v1"
