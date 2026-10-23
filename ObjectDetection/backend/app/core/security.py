"""Local passwords (PBKDF2) and short-lived HS256 tokens."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.fernet import Fernet


def hash_password(password: str, iterations: int = 200_000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, hex_digest = stored.split("$", 3)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), int(iters)
    )
    return secrets.compare_digest(digest.hex(), hex_digest)


def create_token(
    *,
    user_id: str,
    username: str,
    role: str,
    secret: str,
    minutes: int,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=minutes),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    if isinstance(token, bytes):
        return token.decode("ascii")
    return token


def decode_token(token: str, secret: str) -> dict[str, Any]:
    data = jwt.decode(token, secret, algorithms=["HS256"])
    if not isinstance(data, dict):
        raise jwt.InvalidTokenError("token payload must be an object")
    return data


def fernet_from_secret(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))
