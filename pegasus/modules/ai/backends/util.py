"""Process helpers shared by local backends."""
import os
import socket
import subprocess


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def physical_cores() -> int:
    try:
        import psutil
        return max(1, psutil.cpu_count(logical=False) or 2)
    except Exception:
        return max(1, (os.cpu_count() or 2) // 2)


def detect_gpu() -> str:
    for binary, tag in (("nvidia-smi", "cuda"), ("rocm-smi", "rocm"),
                        ("vulkaninfo", "vulkan")):
        if subprocess.run(["which", binary], capture_output=True).returncode == 0:
            return tag
    return "cpu"
