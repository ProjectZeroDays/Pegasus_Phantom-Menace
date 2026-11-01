"""Thermal and battery pressure. True means prefer remote."""
import pathlib
import platform
import subprocess

THROTTLE = 80.0


def _temp() -> float | None:
    system = platform.system()
    try:
        if system == "Linux":
            for zone in pathlib.Path("/sys/class/thermal").glob("thermal_zone*"):
                raw = (zone / "temp").read_text().strip()
                return int(raw) / 1000
        if system == "Darwin":
            out = subprocess.run(["pmset", "-g", "therm"], capture_output=True,
                                 text=True, timeout=5).stdout
            for line in out.splitlines():
                if "CPU_Speed_Limit" in line:
                    return 100.0 - float(line.split("=")[-1].strip())
        if system == "Windows":
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "(Get-CimInstance MSAcpi_ThermalZoneTemperature)"
                                  ".CurrentTemperature"], capture_output=True,
                                 text=True, timeout=10).stdout.strip()
            return float(out.split()[0]) / 10 - 273.15
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return None


def _battery() -> float:
    try:
        import psutil
        b = psutil.sensors_battery()
        return b.percent if b else 100.0
    except (ImportError, AttributeError):
        return 100.0


def pressure() -> bool:
    temp = _temp()
    return (temp is not None and temp > THROTTLE) or _battery() < 10
