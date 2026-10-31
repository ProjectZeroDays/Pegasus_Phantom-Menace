#!/usr/bin/env python3
"""Blast radius estimator for autonomy budget."""

def blast_radius_estimator(target: str, payload: str = "") -> tuple:
    target = target.lower()
    low_risk = target.startswith("emulator")
    high_risk = "galaxy" in target or "dns" in payload.lower() or payload.startswith("CVE-")
    mode = "autonomous" if not high_risk and low_risk else ("shadow" if high_risk else "assisted")
    return mode, {"low_risk": low_risk, "high_risk": high_risk, "mode": mode}

if __name__ == '__main__':
    for t,p in [("emulator-5554","CVE-2023-XXXX"),("galaxy-s24-demo","dns_exfil")]:
        mode, meta = blast_radius_estimator(t,p)
        print(f"Target={t} Payload={p} -> mode={mode} meta={meta}")
