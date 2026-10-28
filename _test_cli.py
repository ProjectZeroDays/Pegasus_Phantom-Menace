"""Smoke-test harness for Pegasus CLI options (runs each scenario in its own process)."""
import os
import subprocess
import sys
import time

from _license_secret import LICENSE_KEY_PLAINTEXT as KEY
SCRIPT = "pegasus_v_1.4.py"
ENV = {**os.environ, "PYTHONUTF8": "1"}

# --- hygiene: wake device and extend screen timeout before first case ---
subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_WAKEUP"], capture_output=True)
subprocess.run(["adb", "shell", "settings", "put", "system", "screen_off_timeout", "1800000"], capture_output=True)

results = []


def run_case(name, inputs, timeout=90):
    data = KEY + "\n" + ("\n".join(inputs) + "\n" if inputs else "")
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, SCRIPT], input=data, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=ENV, cwd=os.getcwd())
    except subprocess.TimeoutExpired:
        results.append((name, False, "TIMEOUT", 0))
        return ""
    out = (r.stdout or "") + (r.stderr or "")
    problems = []
    if r.returncode != 0:
        problems.append(f"exit={r.returncode}")
    if "Traceback" in out:
        # capture the last traceback line for debugging
        lines = [l for l in out.splitlines() if l.strip().startswith((",", "File", "Error")) or "Error" in l]
        problems.append("TRACEBACK: " + (lines[-1][:120] if lines else "?"))
    if "Exiting Pegasus" not in out:
        problems.append("no clean-exit marker")
    results.append((name, not problems, "; ".join(problems), round(time.time() - t0, 1)))
    return out


def check(cond, name, detail=""):
    results.append((name, bool(cond), "" if cond else f"FAILED {detail}", 0))


def size(path):
    return os.path.getsize(path) if os.path.exists(path) else 0


# --- prepare test fixtures ---
with open("test_push.txt", "w") as f:
    f.write("pegasus-push-test-content-12345\n")
for stale in ("screen.png", "record.mp4", "test_pull.txt"):
    if os.path.exists(stale):
        os.remove(stale)

# --- scenarios ---
run_case("1  check_device", [])
out = run_case("6  apk_list", ["6", "y"])
check("package:" in open("apk_list.txt", encoding="utf-8", errors="replace").read()
      if os.path.exists("apk_list.txt") else False, "6  apk_list artifact", "apk_list.txt missing/empty")
run_case("7  screenshot", ["7", "n"])
check(size("screen.png") > 1000, "7  screenshot artifact", f"screen.png={size('screen.png')}")
run_case("19 check_storage", ["19", "n"])
run_case("17 device_logs", ["17", "n"])
check(size("device_log.txt") > 100, "17 log artifact", f"={size('device_log.txt')}")
run_case("23 history", ["23"])
run_case("14 dump_contacts", ["14", "n"])
run_case("16 start_app", ["16", "com.android.settings"])
run_case("12 push_file", ["12", "test_push.txt", "/sdcard/pegasus_test.txt"])
run_case("11 pull_file", ["11", "/sdcard/pegasus_test.txt", "test_pull.txt"])
check(os.path.exists("test_pull.txt") and
      open("test_pull.txt").read() == "pegasus-push-test-content-12345\n",
      "11 pull content match", "file missing or content differs")
run_case("18 wifi_disable", ["18", "disable"])
time.sleep(1)
wifi = subprocess.run(["adb", "shell", "settings", "get", "global", "wifi_on"],
                      capture_output=True, text=True).stdout.strip()
check(wifi in ("0", "disabled"), "18 wifi actually off", f"wifi_on={wifi}")
run_case("18 wifi_enable", ["18", "enable"])
time.sleep(1)
wifi = subprocess.run(["adb", "shell", "settings", "get", "global", "wifi_on"],
                      capture_output=True, text=True).stdout.strip()
check(wifi in ("1", "enabled"), "18 wifi actually on", f"wifi_on={wifi}")
run_case("4  screen_record", ["4", "3", "n"], timeout=60)
check(size("record.mp4") > 1000, "4  record artifact", f"record.mp4={size('record.mp4')}")
run_case("3  disconnect noop", ["3"])
run_case("2  connect abort", ["2", "n", ""])
run_case("22 cyber_root", ["22", "1", "", "0"])
run_case("22 cyber_audit", ["22", "3", "", "0"])
run_case("99 invalid option", ["99"])
run_case("24 scan_network", ["24"])
run_case("25 pair_menu", ["25", "0"])
run_case("21 troubleshoot", ["21"], timeout=60)
time.sleep(4)
run_case("22 cyber_permissions", ["22", "2", "", "0"], timeout=150)
run_case("22 cyber_debuggable", ["22", "4", "", "0"], timeout=150)
devs = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout
check("emulator-5554" in devs, "21 emulator back after adb restart", devs.replace("\n", "|")[:100])

# license negative test
try:
    r = subprocess.run([sys.executable, SCRIPT], input="WRONGKEY\n", capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=30, env=ENV)
    check(r.returncode == 1 and "Invalid license key" in ((r.stdout or "") + (r.stderr or "")),
          "license rejection (old/bad key)", f"exit={r.returncode}")
except subprocess.TimeoutExpired:
    check(False, "license rejection (old/bad key)", "TIMEOUT")

# --- summary ---
print("\n===== TEST SUMMARY =====")
fails = 0
for name, ok, detail, secs in results:
    mark = "PASS" if ok else "FAIL"
    if not ok:
        fails += 1
    print(f"[{mark}] {name:<28} {detail}{'  (' + str(secs) + 's)' if secs else ''}")
print(f"\n{len(results) - fails}/{len(results)} passed")
sys.exit(1 if fails else 0)
