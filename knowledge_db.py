#!/usr/bin/env python3
"""Knowledge base with decay: confidence, source, expiry."""

KB = {
    "protocol_sm_peddlecheap": {"confidence": 0.95, "source": "pcap/replay", "expiry": "v2.1.0", "facts": {"header_bytes": 16}},
    "nso_pegasus_vector": {"confidence": 0.88, "source": "binary", "expiry": "v3.0.0", "facts": {"capabilities": 30}},
}

def retrieve(key: str, version: str):
    entry = KB.get(key)
    if not entry: return None
    if entry.get("expiry") < version: return None  # decayed
    return entry
if __name__ == '__main__':
    print(retrieve("protocol_sm_peddlecheap", "v3.0.0"))
