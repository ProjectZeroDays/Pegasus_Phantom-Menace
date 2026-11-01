"""Role + platform + RAM tier -> (repo, quant, backend)."""
import platform
import sys
from enum import Enum

import psutil


class Role(str, Enum):
    PLANNER = "planner"
    CODER = "coder"


def ram_gb() -> float:
    return psutil.virtual_memory().total / 1e9


def os_key() -> str:
    if sys.platform == "darwin":
        return "macos" if platform.machine() == "arm64" else "macos_intel"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


CATALOG: dict[tuple[Role, str], dict[str, tuple[str, str, str]]] = {
    (Role.PLANNER, "macos"): {
        ">=16": ("mlx-community/Qwen3-4B-Instruct-2507-4bit-DWQ-2510", "mlx", "mlx"),
        "<16": ("mlx-community/Josiefied-Qwen3-1.7B-abliterated-v1-4bit", "mlx", "mlx")},
    (Role.PLANNER, "macos_intel"): {
        ">=16": ("huihui-ai/Qwen2.5-3B-Instruct-abliterated", "Q4_K_M", "llamacpp"),
        "<16": ("huihui-ai/Llama-3.2-3B-Instruct-abliterated", "Q4_K_M", "llamacpp")},
    (Role.PLANNER, "windows"): {
        ">=16": ("backpropSukuna/Qwen3-4B-Instruct-Uncensored", "Q4_K_M", "llamacpp"),
        "<16": ("huihui-ai/Qwen2.5-3B-Instruct-abliterated", "Q4_K_M", "llamacpp")},
    (Role.PLANNER, "linux"): {
        ">=16": ("backpropSukuna/Qwen3-4B-Instruct-Uncensored", "Q4_K_M", "llamacpp"),
        "<16": ("huihui-ai/Qwen2.5-3B-Instruct-abliterated", "Q4_K_M", "llamacpp")},
    (Role.CODER, "macos"): {
        ">=32": ("mlx-community/Qwen3-32B-abliterated-4bit", "mlx", "mlx"),
        ">=16": ("mlx-community/Josiefied-Qwen3-8B-abliterated-v1-4bit", "mlx", "mlx"),
        "<16": ("mlx-community/Josiefied-Qwen3-4B-abliterated-v1-4bit", "mlx", "mlx")},
    (Role.CODER, "macos_intel"): {
        ">=16": ("Qwen2.5-Coder-7B-Instruct-abliterated", "Q4_K_M", "llamacpp"),
        "<16": ("bartowski/Qwen2.5-Coder-3B-Instruct-abliterated", "Q4_K_M", "llamacpp")},
    (Role.CODER, "windows"): {
        ">=32": ("Qwen2.5-Coder-14B-Instruct-abliterated", "Q4_K_M", "llamacpp"),
        ">=16": ("Qwen2.5-Coder-7B-Instruct-abliterated", "Q4_K_M", "llamacpp"),
        "<16": ("bartowski/Qwen2.5-Coder-3B-Instruct-abliterated", "Q4_K_M", "llamacpp")},
    (Role.CODER, "linux"): {
        ">=32": ("Qwen2.5-Coder-14B-Instruct-abliterated", "Q4_K_M", "llamacpp"),
        ">=16": ("Qwen2.5-Coder-7B-Instruct-abliterated", "Q4_K_M", "llamacpp"),
        "<16": ("bartowski/Qwen2.5-Coder-3B-Instruct-abliterated", "Q4_K_M", "llamacpp")},
}

ORDER = (">=32", ">=16", "<16")


def _matches(key: str) -> bool:
    g = ram_gb()
    if key == ">=32":
        return g >= 32
    if key == ">=16":
        return g >= 16
    return g < 16


def resolve(role: Role) -> tuple[str, str, str]:
    table = CATALOG.get((role, os_key()))
    if not table:
        raise LookupError(f"no catalog for {role} on {os_key()}")
    for key in ORDER:
        if key in table and _matches(key):
            return table[key]
    return table["<16"]
