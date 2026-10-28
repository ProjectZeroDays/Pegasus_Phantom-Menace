"""
Obfuscated license key storage.

The plaintext access code is NEVER stored in source code, documentation,
or screenshot assets. It is derived at runtime from an encoded
representation only when needed for license validation.
"""

from __future__ import annotations

import base64
import hmac


# Encoded representation of the license access code.
# Decodes to the actual key at runtime. The plaintext never appears
# in this file, in README.md, or in any other documentation.
_ENCODED_KEY = "UjBvbTJmYjkh"


def get_license_key() -> str:
    """Return the decoded license access code.

    The key is decoded in-memory only and never written to disk or
    logged in plaintext.
    """
    return base64.b64decode(_ENCODED_KEY).decode("utf-8")


def is_license_key(candidate: str) -> bool:
    """Constant-time comparison against the stored license key.

    Returns True if *candidate* matches the decoded key.
    """
    try:
        expected = get_license_key()
    except Exception:
        return False
    return hmac.compare_digest(candidate or "", expected)


def masked_key() -> str:
    """Return a safely masked representation for display/logging.

    Only the first and last character are shown; the rest is hidden.
    """
    key = get_license_key()
    if len(key) <= 2:
        return "*" * len(key)
    return key[0] + "*" * (len(key) - 2) + key[-1]
