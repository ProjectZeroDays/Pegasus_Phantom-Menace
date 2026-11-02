#!/usr/bin/env python3
"""Observability: 'why' chain from finding -> evidence -> action + cost per phase."""
class WhyChain:
    def __init__(self):
        self.steps = []
    def add(self, finding, evidence, action, cost_ms, phase):
        self.steps.append({"finding": finding, "evidence": evidence, "action": action, "cost_ms": cost_ms, "phase": phase})
    def trace(self):
        return self.steps

def observe():
    w = WhyChain()
    w.add("NUL stub found", "memory_diff pcap_1", "quarantine", 120, "persist")
    w.add("Header aligned", "replay pcap_2", "promote", 340, "exfil")
    return w.trace()
if __name__ == '__main__':
    print("Observability trace:", observe())
