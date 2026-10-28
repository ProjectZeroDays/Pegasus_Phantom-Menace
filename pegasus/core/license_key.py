"""
Obfuscated license key storage.

The plaintext access code is NEVER stored in source code, documentation,
or screenshot assets. Only a SHA-256 hash is stored, and license
validation is performed by hashing the candidate at runtime and
comparing digests. The plaintext never appears in this file, in
README.md, or in any other documentation.
"""

from __future__ import annotations

import hashlib
import hmac


# SHA-256 hash of the license access code.
# The plaintext is never stored; validation hashes the candidate at
# runtime and compares digests.
_LICENSE_KEY_HASH = "0e69ee49bec7089cf2fa9c94d0ead455f2be3553c0484de49d303a0193365e67"


def is_license_key(candidate: str) -> bool:
    """Constant-time comparison against the stored license key hash.

    Returns True if SHA-256(candidate) matches the stored hash.
    The plaintext key is never reconstructed in memory.
    """
    if not candidate:
        return False
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, _LICENSE_KEY_HASH)


def masked_key() -> str:
    """Return a fully masked representation for display/logging.

    Only asterisks are shown; no part of the real key is revealed.
    """
    return "*********"


def verify_license_key(candidate: str) -> bool:
    """Alias for is_license_key for readability in calling code."""
    return is_license_key(candidate)
