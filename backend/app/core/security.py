"""Project API tokens.

Format: ``fr_<8 hex prefix>_<secret>``. Only the SHA-256 hash is stored; the prefix is
stored in clear so a token can be found without scanning every hash.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass

TOKEN_SCHEME = "fr"
PREFIX_HEX_LENGTH = 8


@dataclass(frozen=True)
class NewToken:
    value: str
    prefix: str
    hash: str


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> NewToken:
    prefix = secrets.token_hex(PREFIX_HEX_LENGTH // 2)
    value = f"{TOKEN_SCHEME}_{prefix}_{secrets.token_urlsafe(32)}"
    return NewToken(value=value, prefix=prefix, hash=hash_token(value))


def token_prefix(token: str) -> str | None:
    """Return the lookup prefix of a well-formed token, or None."""
    parts = token.split("_", 2)
    if len(parts) != 3 or parts[0] != TOKEN_SCHEME or not parts[2]:
        return None
    prefix = parts[1]
    if len(prefix) != PREFIX_HEX_LENGTH or any(c not in "0123456789abcdef" for c in prefix):
        return None
    return prefix


def token_matches(token: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), stored_hash)


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


# --- Passwords (scrypt from the standard library) -------------------------------------------

SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_LEN = 2**14, 8, 1, 64


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_LEN
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(digest_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)
