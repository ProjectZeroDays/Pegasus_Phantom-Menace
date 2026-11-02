#!/usr/bin/env python3
"""Self-healing supervisor + invariant monitors."""

def quarantine(step: str, reason: str):
    print(f"QUARANTINE: step={step} reason={reason} -> revert to last known good from journal")

def revert_to_journal():
    print("REVERT: rolling back to last good state from pcap_engine/journal.db")

def alert(msg: str):
    print(f"ALERT: {msg}")

if __name__ == '__main__':
    # Violation example: NUL stub or port revert
    quarantine("frame_parsed", "NUL stub detected at header")
    revert_to_journal()
