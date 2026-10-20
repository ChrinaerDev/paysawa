"""Password hashing (stdlib scrypt), dashboard JWTs, API keys, ids, webhook signatures."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt

_N, _R, _P = 2**14, 8, 1


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(
            password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# ---------------------------------------------------------------- dashboard JWT
def create_access_token(merchant_id: uuid.UUID, secret: str, ttl_hours: int = 12) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(merchant_id), "typ": "dashboard", "iat": now, "exp": now + timedelta(hours=ttl_hours)}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> uuid.UUID:
    """Raises jwt.PyJWTError / ValueError on any problem."""
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    if payload.get("typ") != "dashboard":
        raise ValueError("wrong token type")
    return uuid.UUID(payload["sub"])


# ---------------------------------------------------------------- API keys
KEY_PREFIX_LEN = 16  # "sk_test_" / "sk_live_" + 8 random chars


def generate_api_key(mode: str) -> tuple[str, str, str]:
    """Returns (full_secret, prefix, sha256_hash). Only prefix and hash are stored."""
    if mode not in ("test", "live"):
        raise ValueError("mode must be test or live")
    full = f"sk_{mode}_{secrets.token_urlsafe(32)}"
    return full, full[:KEY_PREFIX_LEN], hash_api_key(full)


def derive_api_key(mode: str, key_id: uuid.UUID, secret: str) -> str:
    """Deterministic secret for a key id: lets the dashboard/CLI reveal it again at any time without
    storing it. The database only holds its sha256, so a database leak alone exposes no key."""
    mac = hmac.new(secret.encode(), f"paysawa-api-key:{mode}:{key_id}".encode(), hashlib.sha256).digest()
    return f"sk_{mode}_{_b64(mac)}"


def make_api_key(mode: str, key_id: uuid.UUID, secret: str) -> tuple[str, str, str]:
    """Returns (full_secret, prefix, sha256_hash) for a revealable key."""
    if mode not in ("test", "live"):
        raise ValueError("mode must be test or live")
    full = derive_api_key(mode, key_id, secret)
    return full, full[:KEY_PREFIX_LEN], hash_api_key(full)


def hash_api_key(full: str) -> str:
    return hashlib.sha256(full.encode()).hexdigest()


# ---------------------------------------------------------------- ids and secrets
def new_public_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(10)}"


def new_app_username() -> str:
    return "pa_" + secrets.token_hex(8)


def derive_app_password(app_id: uuid.UUID, secret: str) -> str:
    """Revealable like API keys: derived from a server secret, only its sha256 is stored."""
    mac = hmac.new(secret.encode(), f"paysawa-app-password:{app_id}".encode(), hashlib.sha256).digest()
    return _b64(mac)


def derive_app_webhook_key(app_id: uuid.UUID, secret: str) -> str:
    """Key that signs Campay-style webhooks (JWT HS256). Never stored: always re-derived."""
    mac = hmac.new(secret.encode(), f"paysawa-app-webhook:{app_id}".encode(), hashlib.sha256).digest()
    return "whk_" + _b64(mac)


def create_app_token(app_id: uuid.UUID, secret: str, ttl_seconds: int = 3600) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(app_id), "typ": "app", "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}, secret, algorithm="HS256")


def decode_app_token(token: str, secret: str) -> uuid.UUID:
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    if payload.get("typ") != "app":
        raise ValueError("wrong token type")
    return uuid.UUID(payload["sub"])


def sign_callback(webhook_key: str, params: dict, ttl_seconds: int = 3600) -> str:
    """The `signature` query parameter of a Campay-style webhook: a JWT (HS256) over the other parameters."""
    now = datetime.now(timezone.utc)
    return jwt.encode({**params, "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}, webhook_key, algorithm="HS256")


def new_webhook_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(24)


# ---------------------------------------------------------------- outgoing webhook signatures
def sign_payload(secret: str, body: bytes, timestamp: int) -> str:
    """Header value: t=<unix>,v1=<hex hmac_sha256(secret, f"{t}.{body}")>"""
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def verify_signature(secret: str, body: bytes, header: str, *, tolerance: int = 300, now: int | None = None) -> bool:
    """What merchants run on their side (documented in README)."""
    try:
        parts = dict(item.split("=", 1) for item in header.split(","))
        timestamp = int(parts["t"])
        provided = parts["v1"]
    except (KeyError, ValueError):
        return False
    current = int(time.time()) if now is None else now
    if abs(current - timestamp) > tolerance:
        return False
    expected = sign_payload(secret, body, timestamp).split("v1=", 1)[1]
    return hmac.compare_digest(expected, provided)
