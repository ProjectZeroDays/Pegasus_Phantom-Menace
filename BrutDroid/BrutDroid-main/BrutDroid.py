import os
import sys
import time
import zipfile
import shutil
import requests
import subprocess
import platform
from OpenSSL import crypto
try:
    from termcolor import colored, cprint
    from termcolor import force_color
except ImportError:
    colored = None
    cprint = None
    force_color = None

# Store custom Frida scripts (name, file_path)
custom_scripts = []

def load_custom_scripts():
    """Load existing Frida scripts from the Fripts directory into custom_scripts, excluding default scripts."""
    global custom_scripts
    custom_scripts = []  # Clear the list to avoid duplicates
    default_scripts = {"SSL-BYE.js", "ROOTER.js", "PintooR.js"}  # Default scripts to exclude
    if os.path.exists("./Fripts"):
        for file_name in os.listdir("./Fripts"):
            if file_name.endswith(".js") and file_name not in default_scripts:
                script_name = os.path.splitext(file_name)[0]  # Remove .js extension
                script_path = os.path.join("./Fripts", file_name)
                custom_scripts.append((script_name, script_path))

def startup_animation():
    """Display an animated ASCII art sequence at script startup."""
    os.system('cls' if os.name == 'nt' else 'clear')
    frames = [
        """
        \033[1;31m
    ____             __  ____             _     __
   / __ )_______  __/ /_/ __ \_________  (_)___/ /
  / __  / ___/ / / / __/ / / / ___/ __ \/ / __  /
 / /_/ / /  / /_/ / /_/ /_/ / /  / /_/ / / /_/ /
/_____/_/   \__,_/\__/_____/_/   \____/_/\__,_/   
                                                  
        \033[0m
        """,
        """
        \033[1;36m
    ____             __  ____             _     __
   / __ )_______  __/ /_/ __ \_________  (_)___/ /
  / __  / ___/ / / / __/ / / / ___/ __ \/ / __  /
 / /_/ / /  / /_/ / /_/ /_/ / /  / /_/ / / /_/ /
/_____/_/   \__,_/\__/_____/_/   \____/_/\__,_/   
                                                  
        Initializing...
        \033[0m
        """,
        """
        \033[1;32m
    ____             __  ____             _     __
   / __ )_______  __/ /_/ __ \_________  (_)___/ /
  / __  / ___/ / / / __/ / / / ___/ __ \/ / __  /
 / /_/ / /  / /_/ / /_/ /_/ / /  / /_/ / / /_/ /
/_____/_/   \__,_/\__/_____/_/   \____/_/\__,_/   
                                                  
        Initializing Systems...
        \033[0m
        """,
        """
        \033[1;31m
    ____             __  ____             _     __
   / __ )_______  __/ /_/ __ \_________  (_)___/ /
  / __  / ___/ / / / __/ / / / ___/ __ \/ / __  /
 / /_/ / /  / /_/ / /_/ /_/ / /  / /_/ / / /_/ /
/_____/_/   \__,_/\__/_____/_/   \____/_/\__,_/   
                                                  
        Systems Online!
        \033[0m
        """
    ]
    for frame in frames:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(frame)
        time.sleep(0.8)
    time.sleep(1)

def display_banner():
    if force_color:
        force_color()
    banner = """
\033[1;31m
    ____             __  ____             _     __
   / __ )_______  __/ /_/ __ \_________  (_)___/ /
  / __  / ___/ / / / __/ / / / ___/ __ \/ / __  /
 / /_/ / /  / /_/ / /_/ /_/ / /  / /_/ / / /_/ /
/_____/_/   \__,_/\__/_____/_/   \____/_/\__,_/

          Made with ❤️ by Brut Security                                     
\033[0m
"""
    tagline = "Android Security Automation | v2.0"
    if colored:
        print(colored(banner, 'red', attrs=['bold']))
        print(colored(tagline, 'yellow', attrs=['bold']))
    else:
        print(banner)
        print("\033[1;33m" + tagline + "\033[0m")

def initial_environment_check():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[1;36m→ Verifying BrutDroid Environment...\033[0m\n")
    checks = [
        ("Python 3.9+ Installation", check_python),
        ("Python PATH Configuration", check_python_path),
        ("ADB PATH Configuration", check_adb),
        ("Frida-Tools Installation", check_frida_tools),
        ("curl Availability", check_curl)
    ]
    results = []
    for name, check_func in checks:
        print(f"\033[1;36m[•] Checking {name}...\033[0m", end="", flush=True)
        time.sleep(0.5)
        success, detail = check_func()
        results.append((name, success, detail))
        status = "\033[1;32m[✓]\033[0m" if success else "\033[1;31m[✖]\033[0m"
        print(f"\r{status} {name}: {detail}")
        if not success:
            print(f"\033[1;33m→ Warning: {detail}\033[0m")
            print(f"\033[1;36m→ Install Instructions: {get_install_prompt(name)}\033[0m")
        print("")
    print("\n\033[1;36m→ Environment Check Summary:\033[0m")
    all_passed = True
    for name, success, _ in results:
        status = "\033[1;32m[✓]\033[0m" if success else "\033[1;31m[✖]\033[0m"
        print(f"  {status} {name}")
        if not success:
            all_passed = False
    result_message = "\033[1;32m✔ Environment Ready! Proceeding to Menu...\033[0m" if all_passed else "\033[1;31m⚠ Fix Issues Before Continuing.\033[0m"
    print(f"\n{result_message}")
    time.sleep(1)
    if not all_passed:
        input("\033[1;36m→ Press Enter to exit and fix issues...\033[0m")
        sys.exit(1)

def get_install_prompt(check_name):
    prompts = {
        "Python 3.9+ Installation": "Download Python 3.9+ from https://www.python.org/downloads/ and install, ensuring 'Add to PATH' is checked.",
        "Python PATH Configuration": "Add Python to your system PATH. Follow: https://docs.python.org/3/using/windows.html#finding-the-python-executable",
        "ADB PATH Configuration": "Download Android SDK Platform-Tools from https://developer.android.com/studio/releases/platform-tools and add the folder to PATH.",
        "Frida-Tools Installation": "Install frida-tools via 'pip install frida-tools' or ensure requirements.txt is installed.",
        "curl Availability": "Install curl from https://curl.se/windows/ or use Git Bash, which includes curl."
    }
    return prompts.get(check_name, "Follow the BrutDroid documentation for setup instructions.")

def check_python():
    if "Microsoft\\WindowsApps\\python.exe" in sys.executable:
        return False, "Microsoft Store Python Detected"
    if sys.version_info < (3, 9):
        return False, "Python 3.9+ Required"
    return True, "Python 3.9+ Installed Successfully"

def check_python_path():
    if not shutil.which("python"):
        return False, "Python Not Found in PATH"
    return True, "Python PATH Configured Correctly"

def check_adb():
    if not shutil.which("adb"):
        return False, "ADB Not Found in PATH"
    return True, "ADB PATH Configured Correctly"

def check_frida_tools():
    if not shutil.which("frida"):
        return False, "frida-tools Not Installed"
    return True, "frida-tools Installed Successfully"

def check_curl():
    if not shutil.which("curl"):
        return False, "curl Not Found in PATH"
    return True, "curl Available"

ADB = "adb"

def is_tool_installed(tool):
    if tool == "frida-tools":
        return shutil.which("frida") is not None
    else:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", tool],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

def install_tool(tool):
    subprocess.run([sys.executable, "-m", "pip", "install", tool])

def install_frida_server():
    os.system('cls' if os.name == 'nt' else 'clear')
    frames = [
        """
        \033[1;31m
        ༼ つ ◕_◕ ༽つ

        Preparing Frida Server...
        \033[0m
        """,
        """
        \033[1;36m
        ⸜(｡˃ ᵕ ˂ )⸝♡

        Downloading Frida Server...
        \033[0m
        """,
        """
        \033[1;32m
        (╥﹏╥)

        Frida Server Ready!
        \033[0m
        """
    ]
    for frame in frames:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(frame)
        time.sleep(1)

    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[1;36m╔══════════════════════════════╗\033[0m")
    print("\033[1;36m║      Install Frida Server     ║\033[0m")
    print("\033[1;36m╚══════════════════════════════╝\033[0m\n")
    print("\033[1;33m→ YOU MUST HAVE AN EMULATOR RUNNING!\033[0m")
    print("\033[1;33m1. Open Android Studio → Device Manager → Virtual Tab\033[0m")
    print("\033[1;33m2. Start your emulator (API 31, x86_64/arm64)\033[0m")
    print("\033[1;33m3. Ensure ADB is connected (run 'adb devices' to verify)\033[0m")
    print("\033[1;35m→ Tip: Frida server enables dynamic instrumentation on the emulator.\033[0m\n")

    try:
        print("\033[1;36m[•] Checking Emulator Connection...\033[0m")
        result = subprocess.getoutput("adb devices")
        if "device" not in result.splitlines()[-1]:
            print("\033[1;31m[✖] No Emulator Detected\033[0m")
            print("\033[1;33m→ Start your emulator in Android Studio and try again.\033[0m")
            print("\033[1;35m→ Tip: Run 'adb devices' to confirm connection.\033[0m")
            input("\033[1;36m→ Press Enter to return to the menu...\033[0m")
            return
        print("\033[1;32m[✓] Emulator Detected\033[0m\n")

        print("\033[1;36m[•] Detecting Emulator Architecture...\033[0m")
        abi = subprocess.check_output(f"{ADB} shell getprop ro.product.cpu.abi", shell=True, text=True).strip()
        print("\033[1;32m[✓] Architecture: {}\033[0m".format(abi))

        print("\033[1;36m[•] Checking Frida Version...\033[0m")
        version = subprocess.check_output("frida --version", shell=True, text=True).strip()
        print("\033[1;32m[✓] Frida Version: {}\033[0m\n".format(version))

        print("\033[1;36m[•] Downloading Frida Server...\033[0m")
        frida_url = f"https://github.com/frida/frida/releases/download/{version}/frida-server-{version}-android-{abi}.xz"
        r = requests.get(frida_url)
        r.raise_for_status()
        with open("frida-server.xz", "wb") as f:
            f.write(r.content)
        print("\033[1;32m[✓] Frida Server Downloaded\033[0m")

        print("\033[1;36m[•] Extracting Frida Server...\033[0m")
        import lzma
        with lzma.open("frida-server.xz") as f_in, open("frida-server", "wb") as f_out:
            f_out.write(f_in.read())
        print("\033[1;32m[✓] Frida Server Extracted\033[0m")

        print("\033[1;36m[•] Pushing Frida Server to Emulator...\033[0m")
        subprocess.run(f"{ADB} push frida-server /data/local/tmp/", shell=True, check=True)
        subprocess.run(f"{ADB} shell chmod +x /data/local/tmp/frida-server", shell=True, check=True)
        print("\033[1;32m[✓] Frida Server Installed Successfully\033[0m\n")

        print("\033[1;35m→ Tip: Start Frida server manually with 'adb shell su -c /data/local/tmp/frida-server &'.\033[0m")
        print("\033[1;35m→ Need Help? Join our Telegram: @BrutSecurity or visit https://frida.re/docs/android/\033[0m")
    except Exception as e:
        print(f"\033[1;31m[✖] Failed to Install Frida Server: {e}\033[0m")
        print("\033[1;33m→ Ensure emulator is running, frida-tools is installed, and internet is available.\033[0m")
        print("\033[1;35m→ Tip: Check 'adb devices' and 'frida --version' for issues.\033[0m")
    input("\033[1;36m→ Press Enter to return to the menu...\033[0m")
    os.system('cls' if os.name == 'nt' else 'clear')

def run_frida_server():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[1;36m→ Starting Frida Server...\033[0m")
    subprocess.call("adb start-server", shell=True)
    result = subprocess.getoutput("adb devices")
    if "device" not in result.splitlines()[-1]:
        print("\033[1;31m[✖] No emulator device detected. Start your emulator.\033[0m")
    else:
        print("\033[1;36m  Launching in background...\033[0m")
        cmd = f'{ADB} shell su -c "nohup /data/local/tmp/frida-server > /dev/null 2>&1 &"'
        subprocess.Popen(cmd, shell=True)
        time.sleep(2)  # Wait for server to start
        print("\033[1;32m[✓] Frida server running.\033[0m")
    input("\033[1;36m→ Press Enter to return to the menu...\033[0m")
    os.system('cls' if os.name == 'nt' else 'clear')

def setup_cert_with_magisk():
    os.system('cls' if os.name == 'nt' else 'clear')
    frames = [
        """
        \033[1;31m
        ◕⩊◕

        Preparing Certificate...
        \033[0m
        """,
        """
        \033[1;36m
        ⸜(｡˃ ᵕ ˂ )⸝♡

        Downloading Certificate...
        \033[0m
        """,
        """
        \033[1;32m
        ₍^. .^₎⟆

        Certificate Ready!
        \033[0m
        """
    ]
    for frame in frames:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(frame)
        time.sleep(1)

    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[1;36m╔══════════════════════════════╗\033[0m")
    print("\033[1;36m║ Install Burp Suite Certificate ║\033[0m")
    print("\033[1;36m╚══════════════════════════════╝\033[0m\n")
    print("\033[1;33m→ YOU MUST PERFORM THESE PREPARATORY STEPS!\033[0m")
    print("\033[1;33m1. Start Burp Suite and set it to listen on 127.0.0.1:8080\033[0m")
    print("\033[1;33m2. In the emulator, go to Settings → Wi-Fi → Modify Network → Advanced Options\033[0m")
    print("\033[1;33m3. Set Proxy to Manual, Hostname to 127.0.0.1, Port to 8080\033[0m")
    print("\033[1;33m4. Ensure the emulator is running and rooted (Magisk installed)\033[0m")
    print("\033[1;35m→ Tip: Proxy settings allow the emulator to fetch the Burp certificate.\033[0m\n")
    print("\033[1;33mWaiting 25s for you to set up the proxy...\033[0m")
    for i in range(25, 0, -1):
        print(f"\r\033[1;36m  {i}s left...\033[0m", end="", flush=True)
        time.sleep(1)
    print("\r\033[1;36m[•] Verifying Emulator Connection...\033[0m")

    try:
        result = subprocess.getoutput("adb devices")
        if "device" not in result.splitlines()[-1]:
            print("\033[1;31m[✖] No Emulator Detected\033[0m")
            print("\033[1;33m→ Start your emulator in Android Studio and try again.\033[0m")
            print("\033[1;35m→ Tip: Run 'adb devices' to confirm connection.\033[0m")
            input("\033[1;36m→ Press Enter to return to the menu...\033[0m")
            return
        print("\033[1;32m[✓] Emulator Detected\033[0m\n")

        print("\033[1;36m[•] Downloading Burp Certificate...\033[0m")
        response = requests.get("http://127.0.0.1:8080/cert", timeout=10)
        response.raise_for_status()
        with open("cacert.der", "wb") as f:
            f.write(response.content)
        cert = crypto.load_certificate(crypto.FILETYPE_ASN1, open("cacert.der", "rb").read())
        pem = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
        with open("portswigger.crt", "wb") as f:
            f.write(pem)
        print("\033[1;32m[✓] Certificate Downloaded\033[0m")

        print("\033[1;36m[•] Pushing Certificate to Emulator...\033[0m")
        subprocess.run(f"{ADB} push portswigger.crt /sdcard/portswigger.crt", shell=True, check=True)
        print("\033[1;32m[✓] Certificate Pushed to /sdcard/portswigger.crt\033[0m")

        print("\033[1;36m[•] Fetching AlwaysTrustUserCerts Module...\033[0m")
        try:
            response = requests.get("https://api.github.com/repos/NVISOsecurity/AlwaysTrustUserCerts/releases/latest", timeout=5)
            response.raise_for_status()
            module_version = response.json()["tag_name"]
            filename = f"AlwaysTrustUserCerts_{module_version}.zip"
            module_url = f"https://github.com/NVISOsecurity/AlwaysTrustUserCerts/releases/download/{module_version}/{filename}"
        except (requests.RequestException, KeyError) as e:
            print(f"\033[1;31m[✖] Failed to Fetch Latest Version: {e}\033[0m")
            print("\033[1;33m→ Falling back to v1.3\033[0m")
            module_version = "v1.3"
            filename = f"AlwaysTrustUserCerts_{module_version}.zip"
            module_url = f"https://github.com/NVISOsecurity/AlwaysTrustUserCerts/releases/download/{module_version}/{filename}"

        print(f"\033[1;36m[•] Downloading AlwaysTrustUserCerts {module_version}...\033[0m")
        r = requests.get(module_url)
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        print("\033[1;32m[✓] Module Downloaded\033[0m")

        print("\033[1;36m[•] Installing Magisk Module...\033[0m")
        subprocess.run(f"{ADB} push {filename} /data/local/tmp/", shell=True, check=True)
        subprocess.run(f"{ADB} shell su -c 'magisk --install-module /data/local/tmp/{filename}'", shell=True, check=True)
        print("\033[1;32m[✓] Magisk Module Installed\033[0m\n")

        print("\033[1;33m→ YOU MUST INSTALL THE CERTIFICATE MANUALLY!\033[0m")
        print("\033[1;33m1. On the emulator, go to Settings → Security → Encryption & Credentials\033[0m")
        print("\033[1;33m2. Select 'Install a certificate' → 'CA certificate'\033[0m")
        print("\033[1;33m3. Choose '/sdcard/portswigger.crt'\033[0m")
        print("\033[1;33m4. Name it 'portswigger' and confirm\033[0m")
        print("\033[1;35m→ Tip: This enables Burp Suite to intercept HTTPS traffic.\033[0m\n")
        print("\033[1;33mWaiting 60s for you to install the certificate...\033[0m")
        for i in range(60, 0, -1):
            print(f"\r\033[1;36m  {i}s left...\033[0m", end="", flush=True)
            time.sleep(1)

        print("\r\033[1;36m[•] Rebooting Emulator...\033[0m")
        subprocess.run(f"{ADB} reboot", shell=True, check=True)
        print("\033[1;32m[✓] Setup Complete: Emulator Rebooting\033[0m\n")

        print("\033[1;35m→ Troubleshooting Tips:\033[0m")
        print("\033[1;35m- Proxy Issues? Verify Burp Suite is running on 127.0.0.1:8080.\033[0m")
        print("\033[1;35m- Certificate Not Found? Ensure '/sdcard/portswigger.crt' is on the emulator.\033[0m")
        print("\033[1;35m- Root Issues? Verify Magisk is installed and active.\033[0m")
        print("\033[1;35m- Need Help? Join our Telegram: @BrutSecurity or visit https://portswigger.net/burp/documentation.\033[0m")
    except Exception as e:
        print(f"\033[1;31m[✖] Failed to Install Certificate: {e}\033[0m")
        print("\033[1;33m→ Ensure Burp Suite is running, emulator is rooted, and internet is available.\033[0m")
        print("\033[1;35m→ Tip: Check 'adb devices' and Burp Suite proxy settings.\033[0m")
    input("\033[1;36m→ Press Enter to return to the menu...\033[0m")
    os.system('cls' if os.name == 'nt' else 'clear')

def show_virtual_device_instructions():
    os.system('cls' if os.name == 'nt' else 'clear')
    frames = [
        """
        \033[1;31m
           🤖
          / 0 \\
         ( === )
          `---' 
        Manual AVD Creation
        Step 1: Open Android Studio
        \033[0m
        """,
        """
        \033[1;36m
           🤖
          / 0 \\
         ( === )
          `---' 
        Manual AVD Creation
        Step 2: Create Virtual Device
        \033[0m
        """,
        """
        \033[1;32m
           🤖
          / 0 \\
         ( === )
          `---' 
        Manual AVD Creation
        Step 3: Select System Image
        \033[0m
        """,
        """
        \033[1;31m
           🤖
          / 0 \\
         ( === )
          `---' 
        Manual AVD Creation
        Step 4: Launch Emulator
        \033[0m
        """
    ]
    for frame in frames:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(frame)
        time.sleep(1)

    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[1;31m⚠ THIS IS A MANUAL TASK!\033[0m")
    print("\033[1;36mBrutDroid guides you, but YOU MUST perform these steps in Android Studio.\033[0m\n")
    print("\033[1;93m→ Manual Steps to Create a Virtual Device:\033[0m\n"
          "\033[1;36m1. Open Android Studio\033[0m\n"
          "   - Launch Android Studio on your system.\n"
          "   - Go to 'Device Manager' (right sidebar or 'View > Tool Windows > Device Manager').\n"
          "   - Select the 'Virtual' tab to access AVD Manager.\n\n"
          "\033[1;36m2. Create a New Virtual Device\033[0m\n"
          "   - Click 'Create Virtual Device' in AVD Manager.\n"
          "   - Choose a device (e.g., Pixel 6, Pixel 5, or Pixel 4).\n"
          "   - Click 'Next' to proceed.\n\n"
          "\033[1;36m3. Select System Image\033[0m\n"
          "   - Choose API Level 31 (Android 12) with x86_64 or arm64 architecture.\n"
          "   - If API 31 is not listed, click 'Download' to get it from SDK Manager.\n"
          "   - Select the system image and click 'Next'.\n"
          "   - \033[1;37mWhy API 31? Ensures compatibility with Magisk and Frida.\033[0m\n\n"
          "\033[1;36m4. Configure and Launch Emulator\033[0m\n"
          "   - Accept default AVD settings or customize (e.g., storage, memory).\n"
          "   - Click 'Finish' to create the emulator.\n"
          "   - In AVD Manager, click the green 'Play' button to launch the emulator.\n"
          "   - Verify it boots correctly before proceeding.\n\n"
          "\033[1;93m→ Troubleshooting Tips:\033[0m\n"
          "   - API 31 Missing? Open SDK Manager ('Tools > SDK Manager'), select 'Android 12 (API 31)', and install.\n"
          "   - Emulator Fails to Start? Ensure HAXM/VT-x is enabled in BIOS and Android Studio settings.\n"
          "   - Need Help? Visit https://developer.android.com/studio/run/managing-avds or join our Telegram: @BrutSecurity.\n\n"
          "\033[92m✔ Instructions Complete. Follow the steps above to create your emulator.\033[0m")
    input("\033[96m→ Press Enter to return to the menu...\033[0m")
    os.system('cls' if os.name == 'nt' else 'clear')

def install_magisk_and_patch_rootavd():
    os.system('cls' if os.name == 'nt' else 'clear')
    frames = [
        """
        \033[1;31m
           ╾━╤デ╦︻ (•_- )
        Rooting Emulator
        Step 1: Download Magisk
        \033[0m
        """,
        """
        \033[1;36m
           (̿▀̿ ̿Ĺ̯̿̿▀̿ ̿)̄ 

        Rooting Emulator
        Step 2: Install Magisk
        \033[0m
        """,
        """
        \033[1;32m
           ( ꩜ ᯅ ꩜;)⁭ ⁭ 

        Rooting Emulator
        Step 3: Patch System Image
        \033[0m
        """,
        """
        \033[1;31m
           ( -_•)▄︻━一💥

        Rooting Emulator
        Step 4: Finalize Root
        \033[0m
        """
    ]
    for frame in frames:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(frame)
        time.sleep(0.8)

    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[1;31m⚠ THIS PROCESS INCLUDES MANUAL STEPS!\033[0m")
    print("\033[1;33mBrutDroid automates downloads and patching, but YOU MUST perform manual steps to complete rooting.\033[0m\n")
    
    print("\033[1;36m[•] Checking Emulator Connection...\033[0m")
    result = subprocess.getoutput("adb devices")
    if "device" not in result.splitlines()[-1]:
        print("\033[1;31m[✖] No Emulator Detected\033[0m")
        print("\033[1;33m→ Warning: An emulator must be running to proceed.\033[0m")
        print("\033[1;37m→ Instructions: Start your emulator in Android Studio (API 31, x86_64/arm64) and try again.\033[0m")
        input("\033[96m→ Press Enter to return to the menu...\033[0m")
        return

    print("\033[1;32m[✓] Emulator Detected: Proceeding with Rooting\033[0m\n")
    try:
        print("\033[1;36m[•] Downloading Latest Magisk Version...\033[0m")
        try:
            response = requests.get("https://api.github.com/repos/topjohnwu/Magisk/releases/latest", timeout=5)
            response.raise_for_status()
            magisk_version = response.json()["tag_name"]
            magisk_filename = f"Magisk-{magisk_version}.apk"
            magisk_url = f"https://github.com/topjohnwu/Magisk/releases/download/{magisk_version}/{magisk_filename}"
        except (requests.RequestException, KeyError) as e:
            print(f"\033[1;31m[✖] Failed to Fetch Latest Magisk Version: {e}\033[0m")
            print("\033[1;33m→ Falling Back to Magisk v29.0\033[0m")
            magisk_version = "v29.0"
            magisk_filename = "Magisk-v29.0.apk"
            magisk_url = f"https://github.com/topjohnwu/Magisk/releases/download/{magisk_version}/{magisk_filename}"

        r = requests.get(magisk_url)
        r.raise_for_status()
        with open(magisk_filename, "wb") as f:
            f.write(r.content)
        print(f"\033[1;32m[✓] Successfully Downloaded Magisk {magisk_version}\033[0m\n")

        print("\033[1;36m[•] Installing Magisk to Emulator...\033[0m")
        result = subprocess.run(f"{ADB} install {magisk_filename}", shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"\033[1;31m[✖] Failed to Install Magisk: {result.stderr}\033[0m")
            print("\033[1;33m→ Ensure the emulator is running and ADB is configured correctly.\033[0m")
            input("\033[96m→ Press Enter to return to the menu...\033[0m")
            return
        print("\033[1;32m[✓] Magisk Installed Successfully\033[0m\n")

        print("\033[1;36m[•] Downloading rootAVD for Emulator Patching...\033[0m")
        zip_url = "https://gitlab.com/newbit/rootAVD/-/archive/master/rootAVD-master.zip"
        zip_file = "rootAVD.zip"
        extract_dir = "rootAVD"
        r = requests.get(zip_url)
        r.raise_for_status()
        with open(zip_file, "wb") as f:
            f.write(r.content)
        print("\033[1;32m[✓] Successfully Downloaded rootAVD\033[0m")

        print("\033[1;36m[•] Extracting rootAVD...\033[0m")
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
        print("\033[1;32m[✓] rootAVD Extracted Successfully\033[0m\n")

        print("\033[1;36m[•] Generating System Image List...\033[0m")
        bat_path = os.path.join(extract_dir, "rootAVD-master", "rootAVD.bat")
        bat_dir = os.path.dirname(bat_path)
        cwd = os.getcwd()
        os.chdir(bat_dir)
        result = subprocess.run('cmd /c "rootAVD.bat ListAllAVDs"', shell=True, capture_output=True, text=True)
        os.chdir(cwd)
        
        with open(os.path.join(bat_dir, "rootAVD_list.txt"), "w") as f:
            f.write(result.stdout)
        
        image_paths = set()
        for line in result.stdout.splitlines():
            if line.startswith("rootAVD.bat system-images\\") and "ramdisk.img" in line:
                path = line.split()[1].split("ramdisk.img")[0] + "ramdisk.img"
                image_paths.add(path)
        image_paths = sorted(image_paths)
        
        if not image_paths:
            print("\033[1;31m[✖] No System Images Found\033[0m")
            print("\033[1;33m→ Verify Android SDK is installed and system images are available.\033[0m")
            print("\033[1;37m→ Check rootAVD_list.txt or Android Studio Device Manager for details.\033[0m")
            input("\033[96m→ Press Enter to return to the menu...\033[0m")
            return
        
        print("\033[1;32m[✓] System Images Found:\033[0m")
        for path in image_paths:
            print(f"\033[1;36m  {path}\033[0m")
        print("\033[1;37m→ Note: Full output saved to rootAVD_list.txt for reference.\033[0m\n")

        print("\033[1;33m→ YOU MUST PROVIDE THE SYSTEM IMAGE PATH!\033[0m")
        print("\033[1;33m1. Copy a path from the list above or open Android Studio → Device Manager → Virtual Tab\033[0m")
        print("\033[1;33m2. Select your emulator (API 31, x86_64/arm64)\033[0m")
        print("\033[1;33m3. Click the pencil icon to view details\033[0m")
        print("\033[1;33m4. Note the 'System Image' path (e.g., system-images\\android-31\\google_apis\\x86_64\\ramdisk.img)\033[0m")
        print("\033[1;37m→ Why API 31? Ensures compatibility with Magisk and Frida.\033[0m\n")
        img_path = input("\033[1;36mEnter System Image Path: \033[0m").strip()

        android_home = os.environ.get("ANDROID_HOME", os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"))
        full_img_path = os.path.normpath(os.path.join(android_home, img_path))
        if not os.path.exists(full_img_path):
            print(f"\033[1;31m[✖] Invalid Path: {img_path} does not exist\033[0m")
            print(f"\033[1;33m→ Tried: {full_img_path}\033[0m")
            print("\033[1;33m→ Verify the path in the list above or Android Studio Device Manager.\033[0m")
            print("\033[1;37m→ Ensure ANDROID_HOME is set or system images are in %LOCALAPPDATA%\\Android\\Sdk.\033[0m")
            input("\033[96m→ Press Enter to return to the menu...\033[0m")
            return
        print("\033[1;32m[✓] Valid System Image Path Provided\033[0m\n")

        print("\033[1;36m[•] Patching Emulator System Image...\033[0m")
        os.chdir(bat_dir)
        result = subprocess.run(f'cmd /c ".\\rootAVD.bat {img_path}"', shell=True, capture_output=True, text=True)
        os.chdir(cwd)
        if result.returncode != 0:
            print(f"\033[1;31m[✖] Failed to Patch System Image: {result.stderr}\033[0m")
            print("\033[1;33m→ Ensure the emulator is not running and the path is correct.\033[0m")
            input("\033[96m→ Press Enter to return to the menu...\033[0m")
            return
        print("\033[1;32m[✓] System Image Patched Successfully\033[0m\n")

        print("\033[1;33m→ YOU MUST COLD BOOT THE EMULATOR!\033[0m")
        print("\033[1;33m1. Open Android Studio → Device Manager → Virtual Tab\033[0m")
        print("\033[1;33m2. Select your emulator and click 'More' (three dots) > 'Cold Boot Now'\033[0m")
        print("\033[1;33m3. Wait for the emulator to fully boot\033[0m")
        print("\033[1;37m→ Note: Cold boot ensures the patched image is loaded.\033[0m\n")
        print("\033[1;33m⚠ Waiting 90s for Emulator Cold Boot...\033[0m")
        for i in range(90, 0, -1):
            print(f"\r\033[1;36m  {i}s left...\033[0m", end="", flush=True)
            time.sleep(1)
        print("\r\033[1;36mVerifying Emulator Connection...\033[0m")
        result = subprocess.getoutput("adb devices")
        if "device" not in result.splitlines()[-1]:
            print("\033[1;31m[✖] Emulator Not Connected\033[0m")
            print("\033[1;33m→ Ensure the emulator is running and try again.\033[0m")
            input("\033[96m→ Press Enter to return to the menu...\033[0m")
            return
        print("\033[1;32m[✓] Emulator Connected Successfully\033[0m\n")

        print("\033[1;36m[•] Verifying Root Access...\033[0m")
        result = subprocess.run("adb shell su -c 'echo Root granted'", shell=True, capture_output=True, text=True)
        if result.returncode != 0 or result.stdout.strip() != "Root granted":
            print(f"\033[1;31m[✖] Root Access Not Detected: {result.stderr}\033[0m")
            print("\033[1;33m→ Ensure Magisk is installed and the system image was patched correctly.\033[0m")
            print("\033[1;37m→ Try re-patching the system image or reinstalling Magisk.\033[0m")
            input("\033[96m→ Press Enter to return to the menu...\033[0m")
            return
        print("\033[1;32m[✓] Root Access Confirmed\033[0m\n")

        print("\033[1;33m→ YOU MUST FINALIZE ROOT IN MAGISK!\033[0m")
        print("\033[1;33m1. Open the Magisk app on the emulator\033[0m")
        print("\033[1;33m2. Click 'OK' on the setup popup\033[0m")
        print("\033[1;33m3. Allow the emulator to reboot automatically\033[0m")
        print("\033[1;37m→ Note: This completes the rooting process.\033[0m\n")
        print("\033[1;33mWaiting 30s for Magisk Setup...\033[0m")
        for i in range(30, 0, -1):
            print(f"\r\033[1;36m  {i}s left...\033[0m", end="", flush=True)
            time.sleep(1)
        print("\r\033[1;32m[✓] Root Setup Complete\033[0m")
    except Exception as e:
        print(f"\033[1;31m[✖] Rooting Failed: {e}\033[0m")
        print("\033[1;33m→ Troubleshoot: Check emulator status, internet connection, and logs in rootAVD_list.txt.\033[0m")
    print("\n\033[1;35m→ Troubleshooting Tips:\033[0m")
    print("\033[1;35m- Emulator Issues? Verify API 31 and x86_64/arm64 in Device Manager.\033[0m")
    print("\033[1;35m- ADB Errors? Restart ADB with 'adb kill-server' and 'adb start-server'.\033[0m")
    print("\033[1;35m- Path Issues? Set ANDROID_HOME environment variable or verify system images in %LOCALAPPDATA%\\Android\\Sdk.\033[0m")
    print("\033[1;35m- Root Issues? Re-patch the system image or reinstall Magisk.\033[0m")
    print("\033[1;35m- Need Help? Join our Telegram: @BrutSecurity or visit https://github.com/topjohnwu/Magisk.\033[0m")
    input("\033[96m→ Press Enter to return to the menu...\033[0m")
    os.system('cls' if os.name == 'nt' else 'clear')

def add_custom_frida_script():
    """Prompt user to add a custom Frida script and save it to Fripts directory."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[1;36m╔══════════════════════════════╗\033[0m")
    print("\033[1;36m║      Add Custom Frida Script  ║\033[0m")
    print("\033[1;36m╚══════════════════════════════╝\033[0m\n")
    print("\033[1;35m→ Tip: Paste your Frida script code and give it a unique name.\033[0m\n")
    
    choice = input("\033[1;36mWant to add a script? (y/n): \033[0m").strip().lower()
    if choice != 'y':
        print("\033[1;32m[✓] Script addition cancelled.\033[0m")
        input("\033[1;36m→ Press Enter to return to the menu...\033[0m")
        return False

    print("\033[1;36m[•] Enter your Frida script code (press Enter twice to finish):\033[0m")
    lines = []
    while True:
        line = input()
        if line == "":
            if len(lines) > 0 and lines[-1] == "":
                break
            lines.append("")
        else:
            lines.append(line)
    script_code = "\n".join(lines)

    if not script_code.strip():
        print("\033[1;31m[✖] Error: Script code cannot be empty.\033[0m")
        input("\033[1;36m→ Press Enter to return to the menu...\033[0m")
        return False

    script_name = input("\033[1;36mEnter script name (e.g., MyCustomScript): \033[0m").strip()
    if not script_name:
        print("\033[1;31m[✖] Error: Script name cannot be empty.\033[0m")
        input("\033[1;36m→ Press Enter to return to the menu...\033[0m")
        return False

    # Ensure Fripts directory exists
    os.makedirs("./Fripts", exist_ok=True)
    script_path = os.path.join("./Fripts", f"{script_name}.js")
    
    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_code)
        custom_scripts.append((script_name, script_path))
        print(f"\033[1;32m[✓] Script '{script_name}' saved to {script_path}\033[0m")
        print("\033[1;35m→ Tip: Your script is now available in the Frida Tools menu.\033[0m")
        input("\033[1;36m→ Press Enter to return to the menu...\033[0m")
        return True
    except Exception as e:
        print(f"\033[1;31m[✖] Failed to save script: {e}\033[0m")
        print("\033[1;33m→ Ensure you have write permissions in the Fripts directory.\033[0m")
        input("\033[1;36m→ Press Enter to return to the menu...\033[0m")
        return False

def frida_tool_options():
    """Display enhanced Frida Tools menu with custom script support."""
    # Predefined scripts
    predefined_scripts = {
        "2": ("Bypass SSL Pinning", "SSL-BYE.js"),
        "3": ("Bypass Root Check", "ROOTER.js"),
        "4": ("Bypass SSL + Root", "PintooR.js")
    }

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        # Animation
        frames = [
            """
            \033[1;31m
            (◣ _ ◢)

            Loading Frida Tools...
            \033[0m
            """,
            """
            \033[1;36m
            ⸜(｡˃ ᵕ ˂ )⸝♡

            Preparing Scripts...
            \033[0m
            """,
            """
            \033[1;32m
            (≧ヮ≦) 💕

            Frida Tools Ready!
            \033[0m
            """
        ]
        for frame in frames:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(frame)
            time.sleep(1)

        os.system('cls' if os.name == 'nt' else 'clear')
        display_banner()
        print("\n\033[1;36m╔════════════════════════════╗\033[0m")
        print("\033[1;36m║        Frida Tools         ║\033[0m")
        print("\033[1;36m╚════════════════════════════╝\033[0m\n")
        print("\033[1;36mOptions:\033[0m")
        print("\033[1;37m  1. List Apps\033[0m")
        print("\033[1;35m     - Lists running apps on the emulator\033[0m")
        print("\033[1;37m  2. Bypass SSL Pinning\033[0m")
        print("\033[1;35m     - Disables SSL pinning for HTTPS interception\033[0m")
        print("\033[1;37m  3. Bypass Root Check\033[0m")
        print("\033[1;35m     - Bypasses root detection in apps\033[0m")
        print("\033[1;37m  4. Bypass SSL + Root\033[0m")
        print("\033[1;35m     - Combines SSL pinning and root bypass\033[0m")
        print("\033[1;37m  5. Add Custom Script\033[0m")
        print("\033[1;35m     - Add your own Frida script to the menu\033[0m")
        
        # Display custom scripts
        if custom_scripts:
            print("\033[1;36mCustom Scripts:\033[0m")
            for i, (script_name, _) in enumerate(custom_scripts, 6):
                print(f"\033[1;37m  {i}. {script_name}\033[0m")
                print("\033[1;35m     - Custom Frida script\033[0m")
        
        print(f"\033[1;37m  {6 + len(custom_scripts)}. Back\033[0m\n")
        print("\033[1;35m→ Tip: Ensure emulator is running and rooted for script execution.\033[0m")

        choice = input("\033[1;36m→ Choose: \033[0m")

        if choice == "1":
            os.system('cls' if os.name == 'nt' else 'clear')
            print("\033[1;36m╔════════════════════════════╗\033[0m")
            print("\033[1;36m║        List Apps           ║\033[0m")
            print("\033[1;36m╚════════════════════════════╝\033[0m\n")
            print("\033[1;33m→ YOU MUST HAVE AN EMULATOR RUNNING!\033[0m")
            print("\033[1;33m1. Ensure your emulator is running (API 31, x86_64/arm64)\033[0m")
            print("\033[1;33m2. Verify ADB connection with 'adb devices'\033[0m")
            print("\033[1;35m→ Tip: This lists all running apps for Frida injection.\033[0m\n")
            
            print("\033[1;36m[•] Checking Emulator Connection...\033[0m")
            result = subprocess.getoutput("adb devices")
            if "device" not in result.splitlines()[-1]:
                print("\033[1;31m[✖] No emulator device detected.\033[0m")
                print("\033[1;33m→ Start your emulator in Android Studio.\033[0m")
                input("\033[1;36m→ Press Enter to continue...\033[0m")
                continue
            
            print("\033[1;32m[✓] Emulator Detected\033[0m")
            print("\033[1;36m[•] Listing Applications...\033[0m")
            subprocess.run("frida-ps -Uai", shell=True)
            print("\033[1;32m[✓] Apps Listed Successfully\033[0m")
            print("\033[1;35m→ Tip: Use the package name (e.g., com.example.app) for script injection.\033[0m")
            input("\033[1;36m→ Press Enter to continue...\033[0m")

        elif choice in predefined_scripts:
            script_name, script_file = predefined_scripts[choice]
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"\033[1;36m╔════════════════════════════╗\033[0m")
            print(f"\033[1;36m║        {script_name}        ║\033[0m")
            print(f"\033[1;36m╚════════════════════════════╝\033[0m\n")
            print("\033[1;33m→ YOU MUST HAVE AN EMULATOR RUNNING AND ROOTED!\033[0m")
            print("\033[1;33m1. Ensure your emulator is running (API 31, x86_64/arm64)\033[0m")
            print("\033[1;33m2. Verify root access with 'adb shell su'\033[0m")
            print("\033[1;33m3. Know the target app's package name (e.g., com.example.app)\033[0m")
            print(f"\033[1;35m→ Tip: Use 'List Apps' to find package names.\033[0m\n")
            
            print("\033[1;36m[•] Checking Emulator Connection...\033[0m")
            result = subprocess.getoutput("adb devices")
            if "device" not in result.splitlines()[-1]:
                print("\033[1;31m[✖] No emulator device detected.\033[0m")
                print("\033[1;33m→ Start your emulator in Android Studio.\033[0m")
                input("\033[1;36m→ Press Enter to continue...\033[0m")
                continue
            
            print("\033[1;32m[✓] Emulator Detected\033[0m")
            print("\033[1;36m[•] Requesting Root Access...\033[0m")
            result = subprocess.run("adb shell su -c 'echo Root granted'", shell=True, capture_output=True, text=True)
            if result.returncode != 0 or result.stdout.strip() != "Root granted":
                print("\033[1;31m[✖] Root Access Not Detected\033[0m")
                print("\033[1;33m→ Ensure emulator is rooted with Magisk.\033[0m")
                input("\033[1;36m→ Press Enter to continue...\033[0m")
                continue
            
            print("\033[1;32m[✓] Root Access Granted\033[0m")
            package = input("\033[1;36m→ Enter package name (e.g., com.example.app): \033[0m").strip()
            if not package:
                print("\033[1;31m[✖] Package name cannot be empty.\033[0m")
                input("\033[1;36m→ Press Enter to continue...\033[0m")
                continue
            
            script_path = f"./Fripts/{script_file}"
            if not os.path.exists(script_path):
                print(f"\033[1;31m[✖] Script {script_file} not found.\033[0m")
                print("\033[1;33m→ Ensure {script_file} is in the Fripts directory.\033[0m")
                input("\033[1;36m→ Press Enter to continue...\033[0m")
                continue
            
            print("\033[1;36m[•] Executing {script_name}...\033[0m")
            subprocess.run(f"frida -U -f {package} -l {script_path}", shell=True)
            print(f"\033[1;32m[✓] {script_name} Executed\033[0m")
            print("\033[1;35m→ Tip: Check the emulator for script output or errors.\033[0m")
            input("\033[1;36m→ Press Enter to continue...\033[0m")

        elif choice == "5":
            add_custom_frida_script()

        elif choice.isdigit() and 6 <= int(choice) < 6 + len(custom_scripts):
            index = int(choice) - 6
            script_name, script_path = custom_scripts[index]
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"\033[1;36m╔════════════════════════════╗\033[0m")
            print(f"\033[1;36m║        {script_name}        ║\033[0m")
            print(f"\033[1;36m╚════════════════════════════╝\033[0m\n")
            print("\033[1;33m→ YOU MUST HAVE AN EMULATOR RUNNING AND ROOTED!\033[0m")
            print("\033[1;33m1. Ensure your emulator is running (API 31, x86_64/arm64)\033[0m")
            print("\033[1;33m2. Verify root access with 'adb shell su'\033[0m")
            print("\033[1;33m3. Know the target app's package name (e.g., com.example.app)\033[0m")
            print(f"\033[1;35m→ Tip: Use 'List Apps' to find package names.\033[0m\n")
            
            print("\033[1;36m[•] Checking Emulator Connection...\033[0m")
            result = subprocess.getoutput("adb devices")
            if "device" not in result.splitlines()[-1]:
                print("\033[1;31m[✖] No emulator device detected.\033[0m")
                print("\033[1;33m→ Start your emulator in Android Studio.\033[0m")
                input("\033[1;36m→ Press Enter to continue...\033[0m")
                continue
            
            print("\033[1;32m[✓] Emulator Detected\033[0m")
            print("\033[1;36m[•] Requesting Root Access...\033[0m")
            result = subprocess.run("adb shell su -c 'echo Root granted'", shell=True, capture_output=True, text=True)
            if result.returncode != 0 or result.stdout.strip() != "Root granted":
                print("\033[1;31m[✖] Root Access Not Detected\033[0m")
                print("\033[1;33m→ Ensure emulator is rooted with Magisk.\033[0m")
                input("\033[1;36m→ Press Enter to continue...\033[0m")
                continue
            
            print("\033[1;32m[✓] Root Access Granted\033[0m")
            package = input("\033[1;36m→ Enter package name (e.g., com.example.app): \033[0m").strip()
            if not package:
                print("\033[1;31m[✖] Package name cannot be empty.\033[0m")
                input("\033[1;36m→ Press Enter to continue...\033[0m")
                continue
            
            if not os.path.exists(script_path):
                print(f"\033[1;31m[✖] Script {script_name} not found.\033[0m")
                print("\033[1;33m→ Ensure {script_path} exists in the Fripts directory.\033[0m")
                input("\033[1;36m→ Press Enter to continue...\033[0m")
                continue
            
            print(f"\033[1;36m[•] Executing {script_name}...\033[0m")
            subprocess.run(f"frida -U -f {package} -l {script_path}", shell=True)
            print(f"\033[1;32m[✓] {script_name} Executed\033[0m")
            print("\033[1;35m→ Tip: Check the emulator for script output or errors.\033[0m")
            input("\033[1;36m→ Press Enter to continue...\033[0m")

        elif choice == str(6 + len(custom_scripts)):
            break
        else:
            print("\033[1;31m[✖] Invalid choice. Please select a valid option.\033[0m")
            input("\033[1;36m→ Press Enter to continue...\033[0m")
        os.system('cls' if os.name == 'nt' else 'clear')

def display_main_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        display_banner()
        print("\n\033[96mMain Menu:\033[0m\n"
              "  1. Create Virtual Device\n"
              "  2. Root Emulator\n"
              "  3. Install Tools\n"
              "  4. Configure Emulator\n"
              "  5. Run Frida Server\n"
              "  6. Frida Tools\n"
              "  7. Exit\n")
        choice = input("\033[92m→ Choose: \033[0m")
        if choice == "1":
            show_virtual_device_instructions()
        elif choice == "2":
            install_magisk_and_patch_rootavd()
        elif choice == "3":
            display_windows_tools_menu()
        elif choice == "4":
            display_emulator_options_menu()
        elif choice == "5":
            run_frida_server()
        elif choice == "6":
            frida_tool_options()
        elif choice == "7":
            os.system('cls' if os.name == 'nt' else 'clear')
            print("\033[92m✔ Exiting BrutDroid. Stay sharp!\033[0m")
            break

def display_windows_tools_menu():
    os.system('cls' if os.name == 'nt' else 'clear')
    frames = [
        """
        \033[1;31m
        ᕙ(⇀‸↼‶)ᕗ

        Loading Tools...
        \033[0m
        """,
        """
        \033[1;36m
        (◕‿◕✿)

        Preparing Toolkit...
        \033[0m
        """,
        """
        \033[1;32m
        (⊙_◎)

        Toolkit Ready!
        \033[0m
        """
    ]
    for frame in frames:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(frame)
        time.sleep(1)

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        display_banner()
        print("\n\033[1;36m╔════════════════════════════╗\033[0m")
        print("\033[1;36m║        Install Tools       ║\033[0m")
        print("\033[1;36m╚════════════════════════════╝\033[0m\n")
        
        tools = [
            ("frida", "Core Frida library for dynamic instrumentation"),
            ("frida-tools", "CLI tools for Frida (e.g., frida-ps, frida-trace)"),
            ("objection", "Runtime mobile exploration toolkit for Frida"),
            ("reflutter", "Flutter app reverse engineering tool")
        ]
        
        print("\033[1;36mAvailable Tools:\033[0m")
        for i, (tool, description) in enumerate(tools, 1):
            status = "\033[1;32m[Installed]\033[0m" if is_tool_installed(tool) else "\033[1;33m[Not Installed]\033[0m"
            print(f"\033[1;37m  {i}. {tool:<15}\033[0m {status}")
            print(f"\033[1;35m     - {description}\033[0m")
        print(f"\033[1;37m  5. Back\033[0m\n")
        print("\033[1;35m→ Tip: Select a number to install or update a tool.\033[0m")
        
        choice = input("\033[1;36m→ Choose: \033[0m")
        tool_map = {"1": "frida", "2": "frida-tools", "3": "objection", "4": "reflutter"}
        
        if choice in tool_map:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"\033[1;36m→ Installing {tool_map[choice]}...\033[0m")
            try:
                install_tool(tool_map[choice])
                print(f"\033[1;32m[✓] {tool_map[choice]} installed successfully.\033[0m")
            except Exception as e:
                print(f"\033[1;31m[✖] Failed to install {tool_map[choice]}: {e}\033[0m")
                print("\033[1;33m→ Ensure pip is configured and internet is available.\033[0m")
            input("\033[1;36m→ Press Enter to continue...\033[0m")
        elif choice == "5":
            break
        else:
            print("\033[1;31m[✖] Invalid choice. Please select 1-5.\033[0m")
            input("\033[1;36m→ Press Enter to continue...\033[0m")
        os.system('cls' if os.name == 'nt' else 'clear')

def display_emulator_options_menu():
    os.system('cls' if os.name == 'nt' else 'clear')
    frames = [
        """
        \033[1;31m
        _/\\____/\\ 
        |= ͡° ᆺ ͡°)=
        \\╭☞ \\╭☞ U IS AWESOME!

        Loading Config...
        \033[0m
        """,
        """
        \033[1;36m
        {\\__/}
        (●_●)
        ( > 🍪 Want a cookie?  

        Preparing Emulator...
        \033[0m
        """,
        """
        \033[1;32m
        {\\__/}
        (●_●)
        ( 🍪< No my cookie.

        Emulator Config Ready!
        \033[0m
        """
    ]
    for frame in frames:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(frame)
        time.sleep(1)

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        display_banner()
        print("\n\033[1;36m╔════════════════════════════╗\033[0m")
        print("\033[1;36m║      Configure Emulator    ║\033[0m")
        print("\033[1;36m╚════════════════════════════╝\033[0m\n")
        print("\033[1;36mOptions:\033[0m")
        print("\033[1;37m  1. Install Frida Server\033[0m")
        print("\033[1;35m     - Installs Frida server for dynamic instrumentation\033[0m")
        print("\033[1;37m  2. Install Burp Suite Certificate\033[0m")
        print("\033[1;35m     - Sets up Burp certificate for HTTPS interception\033[0m")
        print("\033[1;37m  3. Back\033[0m\n")
        print("\033[1;35m→ Tip: Ensure emulator is running before selecting an option.\033[0m")
        
        choice = input("\033[1;36m→ Choose: \033[0m")
        if choice == "1":
            install_frida_server()
        elif choice == "2":
            setup_cert_with_magisk()
        elif choice == "3":
            break
        else:
            print("\033[1;31m[✖] Invalid choice. Please select a valid option.\033[0m")
            input("\033[1;36m→ Press Enter to continue...\033[0m")
        os.system('cls' if os.name == 'nt' else 'clear')

if __name__ == "__main__":
    load_custom_scripts()  # Load existing scripts before starting
    startup_animation()
    initial_environment_check()
    os.system('cls' if os.name == 'nt' else 'clear')
    display_main_menu()
