#!/usr/bin/env python3
"""Oracle invariant: clear + length2 ≡ 0 mod 16"""
import sys, sqlite3

def check():
    conn = sqlite3.connect('pcap_engine/journal.db')
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM journal WHERE step_type='frame_parsed' AND (CAST(action AS INTEGER) % 16) != 0")
    violations = cur.fetchone()[0]
    conn.close()
    if violations:
        print(f"FAIL: {violations} invariant violations found")
        sys.exit(1)
    print("PASS: clear+len%16==0 invariant holds (0 violations)")

if __name__ == '__main__':
    check()
