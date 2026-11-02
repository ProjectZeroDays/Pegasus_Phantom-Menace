#!/usr/bin/env python3
"""Idempotent wrapper for POST endpoints."""
import uuid

def build_request(endpoint: str, payload: dict, idempotency_key: str = None):
    return {"endpoint": endpoint, "payload": payload, "key": idempotency_key or str(uuid.uuid4())}

if __name__ == '__main__':
    req = build_request("/api/catalog/build", {"payload":"polymorphic"}, "key-123")
    print("Idempotent request:", req)
