#!/usr/bin/env python3
"""Mutation with provenance: diff against failing case."""

def mutate(case_path: str, hypothesis: str):
    return {"case": case_path, "hypothesis": hypothesis, "patch": "diff against failing", "provenance": "journal.db"}
if __name__ == '__main__':
    print("Mutation ready. Example: mutate('captures/pcap_1.pcap', 'header alignment')")
