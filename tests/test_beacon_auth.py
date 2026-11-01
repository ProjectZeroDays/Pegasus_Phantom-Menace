import hashlib
import hmac
import time

from pegasus.modules.c2 import beacon_routes, dna


def _setup(dna_id="t1", key="00" * 32):
    dna.enrol(dna_id, "serial", key, [])
    return dna_id, key


def _sign(key: str, body: bytes, ts: str) -> str:
    return hmac.new(bytes.fromhex(key), f"{ts}.".encode() + body,
                    hashlib.sha256).hexdigest()


def test_signature_roundtrip():
    dna_id, key = _setup()
    body = b'{"a":1}'
    ts = str(int(time.time()))
    assert beacon_routes._verify(dna_id, body, ts, _sign(key, body, ts))


def test_bad_signature():
    dna_id, _ = _setup("t2")
    assert not beacon_routes._verify(dna_id, b"x", str(int(time.time())), "deadbeef")


def test_stale_timestamp():
    dna_id, key = _setup("t3")
    body, ts = b"x", str(int(time.time()) - 400)
    assert not beacon_routes._verify(dna_id, body, ts, _sign(key, body, ts))


def test_non_numeric_timestamp():
    dna_id, _ = _setup("t4")
    assert not beacon_routes._verify(dna_id, b"x", "abc", "deadbeef")
