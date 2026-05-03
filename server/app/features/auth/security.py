from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


PASSWORD_ITERATIONS = 120_000
TOTP_INTERVAL = 30
TOTP_DIGITS = 6


def hash_password(password: str, salt: str | None = None) -> str:
    salt_value = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_value.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"{salt_value}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, expected_hash = stored_hash.split("$", 1)
    except ValueError:
        return False

    actual_hash = hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(actual_hash, expected_hash)


def generate_access_token() -> str:
    return secrets.token_urlsafe(32)


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8").rstrip("=")


def build_otpauth_url(*, issuer: str, username: str, secret: str) -> str:
    label = quote(f"{issuer}:{username}")
    issuer_encoded = quote(issuer)
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret}&issuer={issuer_encoded}&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_INTERVAL}"
    )


def _normalize_base32(secret: str) -> str:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    return f"{secret.upper()}{padding}"


def generate_totp_code(secret: str, timestamp: int | None = None) -> str:
    counter = int((timestamp or time.time()) // TOTP_INTERVAL)
    counter_bytes = struct.pack(">Q", counter)
    key = base64.b32decode(_normalize_base32(secret), casefold=True)
    digest = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def verify_totp_code(secret: str, code: str, window: int = 1) -> bool:
    normalized = code.strip()
    if not normalized.isdigit():
        return False

    now = int(time.time())
    for delta in range(-window, window + 1):
        if generate_totp_code(secret, now + delta * TOTP_INTERVAL) == normalized:
            return True
    return False
