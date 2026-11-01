import requests, subprocess, sys
base = "http://127.0.0.1:5001"
try:
    r = requests.get(f"{base}/api/health", timeout=5)
    print("health:", r.status_code, r.text)
except Exception as e:
    print("health error:", e)
try:
    r = requests.post(f"{base}/api/beacon/beacon", headers={"X-Dna":"t"}, timeout=5)
    print("beacon unsigned:", r.status_code)
except Exception as e:
    print("beacon error:", e)
# Run verify.py
result = subprocess.run([sys.executable, "scripts/verify.py"], capture_output=True, text=True)
print("verify exit:", result.returncode)
print("verify stdout:", result.stdout)
print("verify stderr:", result.stderr)
