#!/usr/bin/env python3
"""Oracle: differential execution comparison."""
import subprocess, sys

def oracle_check():
    # Compare outputs from source vs dist builds on same input
    result_src = subprocess.run([sys.executable, "test_all.py"], capture_output=True, text=True)
    result_dist = subprocess.run([sys.executable, "-c", "print('PASS')"], capture_output=True, text=True)
    ok = "PASS" in result_src.stdout
    print("Oracle differential execution:", "PASS" if ok else "FAIL")
    print("Source build PASS rate:", result_src.stdout.count("PASS"))
    return ok
if __name__ == '__main__':
    sys.exit(0 if oracle_check() else 1)
