"""
Symmetric encryption for sensitive fields (API keys) using Fernet (AES-128-CBC + HMAC).
The ENCRYPTION_KEY must be a URL-safe base64-encoded 32-byte key stored in .env.
"""

import os
from cryptography.fernet import Fernet, InvalidToken

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ.get("ENCRYPTION_KEY", "").strip()
        if not key:
            raise RuntimeError("ENCRYPTION_KEY is not set in environment / .env")
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string and return a URL-safe base64 token."""
    if not plaintext:
        return plaintext
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet token back to plaintext. Returns the token unchanged if it is not encrypted."""
    if not token:
        return token
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        # Already plaintext (legacy row) or corrupt — return as-is
        return token
