"""
Pegasus Phantom Menace v2 - BrutDroid Module
Android emulator automation: creation, rooting, Frida server, Burp cert, custom scripts.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from rich.table import Table
from rich.panel import Panel

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import CommandInfo, HookType, PluginMetadata
from pegasus.core.config import get_settings


class BrutDroidModule(BaseModule):
    """
    Android Studio pentest automator module.
    Provides emulator creation, rooting (Magisk + rootAVD), Frida server setup,
    Burp Suite certificate installation, and custom Frida script management.
    """

    metadata = PluginMetadata(
        name="brutdroid",
        version="2.0.0",
        description="Android emulator automation - creation, rooting, Frida, Burp cert, custom scripts",
        author="Brut Security",
        category="device",
        tags=["android", "emulator", "root", "frida", "burp", "certificate", "frida-scripts"],
        requires=["rich", "requests"],
        requires_python=">=3.9",
    )

    @property
    def module_name(self) -> str:
        return "BrutDroid"

    @property
    def module_description(self) -> str:
        return "Android emulator automation - creation, rooting, Frida, Burp cert, custom scripts"

    @property
    def module_category(self) -> str:
        return "device"

    async def _register_commands(self) -> None:
        self.register_command("brutdroid-menu", "BrutDroid main menu", self.cmd_brutdroid_menu)
        self.register_command("brutdroid-create-vd", "Create virtual device instructions", self.cmd_create_vd)
        self.register_command("brutdroid-root", "Root emulator with Magisk + rootAVD", self.cmd_root_emulator)
        self.register_command("brutdroid-frida-server", "Install Frida server on emulator", self.cmd_install_frida_server)
        self.register_command("brutdroid-run-frida", "Run Frida server on emulator", self.cmd_run_frida_server)
        self.register_command("brutdroid-burp-cert", "Install Burp Suite certificate", self.cmd_install_burp_cert)
        self.register_command("brutdroid-frida-tools", "Frida tools menu", self.cmd_frida_tools)
        self.register_command("brutdroid-add-script", "Add custom Frida script", self.cmd_add_custom_script)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="brutdroid_dashboard",
            component_type="panel",
            path="/brutdroid",
            title="BrutDroid Dashboard",
            icon="🧨",
            order=3,
        )

    async def _register_hooks(self) -> None:
        pass

    # ── ADB Helpers ──────────────────────────────────────────────────

    def _run_adb(self, command: str, timeout: int = 30) -> subprocess.CompletedProcess:
        """Run an ADB shell command."""
        return subprocess.run(
            ["adb", "shell", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _adb_devices(self) -> str:
        """List connected ADB devices."""
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=15)
        return result.stdout

    def _check_emulator(self) -> bool:
        """Check if an emulator/device is connected via ADB."""
        output = self._adb_devices()
        lines = output.strip().splitlines()
        if len(lines) < 2:
            return False
        last_line = lines[-1].strip()
        return "device" in last_line and "offline" not in last_line

    def _check_root(self) -> bool:
        """Check if the connected device is rooted."""
        result = self._run_adb("su -c 'echo Root granted'", timeout=10)
        return result.returncode == 0 and result.stdout.strip() == "Root granted"

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_brutdroid_menu(self, *args) -> None:
        """BrutDroid interactive menu."""
        self._console.print("\n[bold cyan]BrutDroid - Android Pentest Automator v2.0[/bold cyan]\n")

        menu = {
            "1": ("Create Virtual Device", self.cmd_create_vd),
            "2": ("Root Emulator", self.cmd_root_emulator),
            "3": ("Install Frida Server", self.cmd_install_frida_server),
            "4": ("Run Frida Server", self.cmd_run_frida_server),
            "5": ("Install Burp Certificate", self.cmd_install_burp_cert),
            "6": ("Frida Tools", self.cmd_frida_tools),
            "7": ("Add Custom Frida Script", self.cmd_add_custom_script),
            "8": ("Back", None),
        }

        while True:
            self._console.print("\n[bold]BrutDroid Menu:[/bold]")
            for k, (desc, _) in menu.items():
                self._console.print(f"  [{k}] {desc}")
            choice = self.prompt("Select option", choices=list(menu.keys()), default="8")

            if choice == "8":
                break

            _, handler = menu[choice]
            if handler:
                await handler()

    async def cmd_create_vd(self, *args) -> None:
        """Display virtual device creation instructions."""
        self._console.print("\n[bold cyan]Create Virtual Device[/bold cyan]\n")
        self._console.print("[yellow]This is a manual task performed in Android Studio.[/yellow]\n")
        self._console.print("1. Open Android Studio → Device Manager → Virtual tab")
        self._console.print("2. Click 'Create Virtual Device'")
        self._console.print("3. Choose a device (e.g., Pixel 6, Pixel 5)")
        self._console.print("4. Select system image: API 31 (Android 12), x86_64 or arm64")
        self._console.print("5. Configure and launch the emulator")
        self._console.print("\n[dim]Why API 31? Ensures compatibility with Magisk and Frida.[/dim]")
        self.prompt("Press Enter to continue...")

    async def cmd_root_emulator(self, *args) -> None:
        """Root emulator with Magisk + rootAVD."""
        if not self._check_emulator():
            self.print_error("No emulator detected. Start an emulator in Android Studio first.")
            self.prompt("Press Enter to continue...")
            return

        self.print_success("Emulator detected")
        self._console.print("\n[cyan]► Downloading Magisk...[/cyan]")
        try:
            import requests
            try:
                resp = requests.get(
                    "https://api.github.com/repos/topjohnwu/Magisk/releases/latest",
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                magisk_version = data["tag_name"]
                magisk_file = f"Magisk-{magisk_version}.apk"
                magisk_url = f"https://github.com/topjohnwu/Magisk/releases/download/{magisk_version}/{magisk_file}"
            except Exception:
                self.print_warning("Could not fetch latest Magisk version, using v29.0")
                magisk_version = "v29.0"
                magisk_file = "Magisk-v29.0.apk"
                magisk_url = f"https://github.com/topjohnwu/Magisk/releases/download/{magisk_version}/{magisk_file}"

            r = requests.get(magisk_url, timeout=60)
            r.raise_for_status()
            magisk_path = Path(magisk_file)
            magisk_path.write_bytes(r.content)
            self.print_success(f"Downloaded Magisk {magisk_version}")

            self._console.print("[cyan]► Installing Magisk to emulator...[/cyan]")
            result = subprocess.run(
                f"adb install {magisk_file}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                self.print_error(f"Failed to install Magisk: {result.stderr}")
                magisk_path.unlink(missing_ok=True)
                self.prompt("Press Enter to continue...")
                return

            self.print_success("Magisk installed successfully")
            magisk_path.unlink(missing_ok=True)

        except Exception as e:
            self.print_error(f"Failed to download/install Magisk: {e}")
            self.prompt("Press Enter to continue...")
            return

        self._console.print("\n[cyan]► Downloading rootAVD...[/cyan]")
        try:
            import requests
            zip_url = "https://gitlab.com/newbit/rootAVD/-/archive/master/rootAVD-master.zip"
            zip_file = "rootAVD.zip"
            extract_dir = "rootAVD"

            r = requests.get(zip_url, timeout=60)
            r.raise_for_status()
            Path(zip_file).write_bytes(r.content)
            self.print_success("Downloaded rootAVD")

            with zipfile.ZipFile(zip_file, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            self.print_success("rootAVD extracted")

            bat_path = Path(extract_dir) / "rootAVD-master" / "rootAVD.bat"
            bat_dir = str(bat_path.parent)
            cwd = os.getcwd()
            os.chdir(bat_dir)

            result = subprocess.run(
                'cmd /c "rootAVD.bat ListAllAVDs"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            os.chdir(cwd)

            list_path = Path(bat_dir) / "rootAVD_list.txt"
            list_path.write_text(result.stdout)

            image_paths = set()
            for line in result.stdout.splitlines():
                if line.startswith("rootAVD.bat system-images\\") and "ramdisk.img" in line:
                    path = line.split()[1].split("ramdisk.img")[0] + "ramdisk.img"
                    image_paths.add(path)

            if not image_paths:
                self.print_error("No system images found")
                self.prompt("Press Enter to continue...")
                return

            self.print_success(f"Found {len(image_paths)} system image(s)")
            for path in sorted(image_paths):
                self._console.print(f"  {path}")

            self._console.print("\n[yellow]⚠ You must provide the system image path![/yellow]")
            self._console.print("1. Copy a path from the list above")
            self._console.print("2. Or: Android Studio → Device Manager → Virtual Tab → pencil icon → System Image path")
            img_path = self.prompt("Enter System Image Path")

            android_home = os.environ.get(
                "ANDROID_HOME",
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"),
            )
            full_img_path = os.path.normpath(os.path.join(android_home, img_path))

            if not os.path.exists(full_img_path):
                self.print_error(f"Invalid path: {full_img_path} does not exist")
                self.prompt("Press Enter to continue...")
                return

            self.print_success("Valid system image path")

            self._console.print("[cyan]► Patching system image...[/cyan]")
            os.chdir(bat_dir)
            result = subprocess.run(
                f'cmd /c ".\\rootAVD.bat {img_path}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            os.chdir(cwd)

            if result.returncode != 0:
                self.print_error(f"Failed to patch: {result.stderr}")
                self.prompt("Press Enter to continue...")
                return

            self.print_success("System image patched successfully")

            self._console.print("\n[yellow]⚠ You must cold boot the emulator![/yellow]")
            self._console.print("1. Android Studio → Device Manager → Virtual Tab")
            self._console.print("2. Select emulator → More (three dots) → Cold Boot Now")
            self._console.print("3. Wait for full boot")

            self._console.print("\n[yellow]Waiting 90s for cold boot...[/yellow]")
            for i in range(90, 0, -1):
                print(f"\r  {i}s left...", end="", flush=True)
                time.sleep(1)
            print()

            if not self._check_emulator():
                self.print_error("Emulator not connected after cold boot")
                self.prompt("Press Enter to continue...")
                return

            self.print_success("Emulator connected")

            self._console.print("[cyan]► Verifying root access...[/cyan]")
            if self._check_root():
                self.print_success("Root access confirmed")
            else:
                self.print_error("Root access not detected")
                self._console.print("Open Magisk app on emulator and complete setup")

            self._console.print("\n[yellow]⚠ Finalize root in Magisk app![/yellow]")
            self._console.print("1. Open Magisk app on emulator")
            self._console.print("2. Click 'OK' on setup popup")
            self._console.print("3. Allow emulator to reboot")

            for i in range(30, 0, -1):
                print(f"\r  {i}s left...", end="", flush=True)
                time.sleep(1)
            print()
            self.print_success("Root setup complete")

        except Exception as e:
            self.print_error(f"Rooting failed: {e}")

        self.prompt("Press Enter to continue...")

    async def cmd_install_frida_server(self, *args) -> None:
        """Install Frida server on the emulator."""
        if not self._check_emulator():
            self.print_error("No emulator detected")
            self.prompt("Press Enter to continue...")
            return

        try:
            import requests
            import lzma

            self._console.print("[cyan]► Checking emulator connection...[/cyan]")
            self.print_success("Emulator detected")

            result = self._run_adb("getprop ro.product.cpu.abi")
            abi = result.stdout.strip()
            self.print_success(f"Architecture: {abi}")

            result = subprocess.run(["frida", "--version"], capture_output=True, text=True, timeout=10)
            frida_version = result.stdout.strip()
            self.print_success(f"Frida version: {frida_version}")

            frida_url = (
                f"https://github.com/frida/frida/releases/download/{frida_version}"
                f"/frida-server-{frida_version}-android-{abi}.xz"
            )

            self._console.print("[cyan]► Downloading Frida server...[/cyan]")
            r = requests.get(frida_url, timeout=120)
            r.raise_for_status()
            Path("frida-server.xz").write_bytes(r.content)
            self.print_success("Frida server downloaded")

            self._console.print("[cyan]► Extracting...[/cyan]")
            with lzma.open("frida-server.xz") as f_in, open("frida-server", "wb") as f_out:
                f_out.write(f_in.read())
            self.print_success("Frida server extracted")

            self._console.print("[cyan]► Pushing to emulator...[/cyan]")
            subprocess.run(["adb", "push", "frida-server", "/data/local/tmp/"], check=True, timeout=30)
            self._run_adb("chmod +x /data/local/tmp/frida-server")
            self.print_success("Frida server installed on emulator")

            Path("frida-server.xz").unlink(missing_ok=True)

        except Exception as e:
            self.print_error(f"Failed to install Frida server: {e}")

        self.prompt("Press Enter to continue...")

    async def cmd_run_frida_server(self, *args) -> None:
        """Run Frida server on the emulator."""
        if not self._check_emulator():
            self.print_error("No emulator detected")
            self.prompt("Press Enter to continue...")
            return

        subprocess.run(["adb", "start-server"], shell=True, capture_output=True)

        if not self._check_root():
            self.print_warning("Root access not detected. Frida server may not start properly.")

        self._console.print("[cyan]► Starting Frida server in background...[/cyan]")
        cmd = 'adb shell su -c "nohup /data/local/tmp/frida-server > /dev/null 2>&1 &"'
        subprocess.Popen(cmd, shell=True)
        time.sleep(2)

        if self._check_root():
            self.print_success("Frida server running")
        else:
            self.print_warning("Frida server may not have started. Ensure emulator is rooted.")

        self.prompt("Press Enter to continue...")

    async def cmd_install_burp_cert(self, *args) -> None:
        """Install Burp Suite certificate on emulator."""
        if not self._check_emulator():
            self.print_error("No emulator detected")
            self.prompt("Press Enter to continue...")
            return

        self._console.print("\n[yellow]⚠ Preparatory steps required:[/yellow]")
        self._console.print("1. Start Burp Suite on 127.0.0.1:8080")
        self._console.print("2. Emulator Wi-Fi → Modify Network → Advanced Options")
        self._console.print("3. Proxy: Manual, 127.0.0.1:8080")
        self._console.print("4. Emulator must be rooted with Magisk\n")

        self.prompt("Press Enter after completing setup...")

        try:
            import requests
            from OpenSSL import crypto

            if not self._check_emulator():
                self.print_error("Emulator disconnected")
                self.prompt("Press Enter to continue...")
                return

            self._console.print("[cyan]► Downloading Burp certificate...[/cyan]")
            resp = requests.get("http://127.0.0.1:8080/cert", timeout=10)
            resp.raise_for_status()
            Path("cacert.der").write_bytes(resp.content)

            cert = crypto.load_certificate(crypto.FILETYPE_ASN1, Path("cacert.der").read_bytes())
            pem = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
            Path("portswigger.crt").write_bytes(pem)
            self.print_success("Certificate downloaded and converted")

            self._console.print("[cyan]► Pushing certificate to emulator...[/cyan]")
            subprocess.run(
                ["adb", "push", "portswigger.crt", "/sdcard/portswigger.crt"],
                check=True,
                timeout=30,
            )
            self.print_success("Certificate pushed to /sdcard/")

            self._console.print("[cyan]► Fetching AlwaysTrustUserCerts Magisk module...[/cyan]")
            try:
                resp = requests.get(
                    "https://api.github.com/repos/NVISOsecurity/AlwaysTrustUserCerts/releases/latest",
                    timeout=10,
                )
                resp.raise_for_status()
                tag = resp.json()["tag_name"]
                filename = f"AlwaysTrustUserCerts_{tag}.zip"
                module_url = (
                    f"https://github.com/NVISOsecurity/AlwaysTrustUserCerts"
                    f"/releases/download/{tag}/{filename}"
                )
            except Exception:
                self.print_warning("Using fallback v1.3")
                tag = "v1.3"
                filename = f"AlwaysTrustUserCerts_{tag}.zip"
                module_url = (
                    f"https://github.com/NVISOsecurity/AlwaysTrustUserCerts"
                    f"/releases/download/{tag}/{filename}"
                )

            r = requests.get(module_url, timeout=60)
            r.raise_for_status()
            Path(filename).write_bytes(r.content)
            self.print_success(f"Module downloaded: {tag}")

            self._console.print("[cyan]► Installing Magisk module...[/cyan]")
            subprocess.run(
                f"adb push {filename} /data/local/tmp/",
                shell=True,
                check=True,
                timeout=30,
            )
            self._run_adb(f"su -c 'magisk --install-module /data/local/tmp/{filename}'")
            self.print_success("Magisk module installed")

            self._console.print("\n[yellow]⚠ Install certificate manually on emulator![/yellow]")
            self._console.print("1. Settings → Security → Encryption & Credentials")
            self._console.print("2. Install a certificate → CA certificate")
            self._console.print("3. Choose /sdcard/portswigger.crt, name it 'portswigger'")

            for i in range(60, 0, -1):
                print(f"\r  {i}s left...", end="", flush=True)
                time.sleep(1)
            print()

            self._console.print("[cyan]► Rebooting emulator...[/cyan]")
            subprocess.run(["adb", "reboot"], check=True, timeout=30)
            self.print_success("Emulator rebooting")

        except Exception as e:
            self.print_error(f"Certificate installation failed: {e}")

        self.prompt("Press Enter to continue...")

    async def cmd_frida_tools(self, *args) -> None:
        """Frida tools menu."""
        if not self._check_emulator():
            self.print_error("No emulator detected")
            self.prompt("Press Enter to continue...")
            return

        predefined = {
            "2": ("Bypass SSL Pinning", "SSL-BYE.js"),
            "3": ("Bypass Root Check", "ROOTER.js"),
            "4": ("Bypass SSL + Root", "PintooR.js"),
        }

        fripts_dir = Path(__file__).parent / "Fripts"
        custom_scripts: List[tuple[str, Path]] = []

        if fripts_dir.exists():
            for f in sorted(fripts_dir.glob("*.js")):
                if f.name not in {"SSL-BYE.js", "ROOTER.js", "PintooR.js"}:
                    custom_scripts.append((f.stem, f))

        while True:
            self._console.print("\n[bold cyan]Frida Tools[/bold cyan]\n")
            self._console.print("  [1] List Apps")
            self._console.print("  [2] Bypass SSL Pinning")
            self._console.print("  [3] Bypass Root Check")
            self._console.print("  [4] Bypass SSL + Root")
            self._console.print("  [5] Add Custom Script")
            for i, (name, _) in enumerate(custom_scripts, 6):
                self._console.print(f"  [{i}] {name}")
            self._console.print(f"  [{6 + len(custom_scripts)}] Back")

            choice = self.prompt("Choose option")

            if choice == "1":
                subprocess.run("frida-ps -Uai", shell=True)
                self.prompt("Press Enter to continue...")

            elif choice in predefined:
                name, script_file = predefined[choice]
                script_path = fripts_dir / script_file
                if not script_path.exists():
                    self.print_error(f"Script {script_file} not found")
                    self.prompt("Press Enter to continue...")
                    continue

                if not self._check_root():
                    self.print_error("Root access required")
                    self.prompt("Press Enter to continue...")
                    continue

                package = self.prompt("Enter package name (e.g., com.example.app)")
                if not package:
                    continue

                self._console.print(f"[cyan]► Executing {name} on {package}...[/cyan]")
                subprocess.run(f"frida -U -f {package} -l {script_path}", shell=True)
                self.prompt("Press Enter to continue...")

            elif choice == "5":
                await self.cmd_add_custom_script()
                # Refresh custom scripts list
                custom_scripts.clear()
                if fripts_dir.exists():
                    for f in sorted(fripts_dir.glob("*.js")):
                        if f.name not in {"SSL-BYE.js", "ROOTER.js", "PintooR.js"}:
                            custom_scripts.append((f.stem, f))

            elif choice.isdigit() and 6 <= int(choice) < 6 + len(custom_scripts):
                idx = int(choice) - 6
                name, script_path = custom_scripts[idx]

                if not self._check_root():
                    self.print_error("Root access required")
                    self.prompt("Press Enter to continue...")
                    continue

                package = self.prompt("Enter package name (e.g., com.example.app)")
                if not package:
                    continue

                self._console.print(f"[cyan]► Executing {name} on {package}...[/cyan]")
                subprocess.run(f"frida -U -f {package} -l {script_path}", shell=True)
                self.prompt("Press Enter to continue...")

            elif choice == str(6 + len(custom_scripts)):
                break
            else:
                self.print_error("Invalid choice")

    async def cmd_add_custom_script(self, *args) -> None:
        """Add a custom Frida script."""
        self._console.print("\n[bold cyan]Add Custom Frida Script[/bold cyan]\n")

        choice = self.prompt("Add a script? (y/n)", choices=["y", "n"], default="n")
        if choice != "y":
            return

        self._console.print("[cyan]► Enter Frida script code (press Enter twice to finish):[/cyan]")
        lines: List[str] = []
        while True:
            line = input()
            if line == "":
                if lines and lines[-1] == "":
                    break
                lines.append("")
            else:
                lines.append(line)

        script_code = "\n".join(lines)
        if not script_code.strip():
            self.print_error("Script code cannot be empty")
            self.prompt("Press Enter to continue...")
            return

        script_name = self.prompt("Enter script name (e.g., MyScript)")
        if not script_name:
            self.print_error("Script name cannot be empty")
            self.prompt("Press Enter to continue...")
            return

        fripts_dir = Path(__file__).parent / "Fripts"
        fripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = fripts_dir / f"{script_name}.js"

        try:
            script_path.write_text(script_code, encoding="utf-8")
            self.print_success(f"Script '{script_name}' saved to {script_path}")
        except Exception as e:
            self.print_error(f"Failed to save script: {e}")

        self.prompt("Press Enter to continue...")
