from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.errors import ApiError
from app.models import ApiKey, App, Merchant
from app.providers.registry import ProviderRegistry
from app.security import KEY_PREFIX_LEN, decode_access_token, decode_app_token, hash_api_key


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "unauthorized", "Missing 'Authorization: Bearer ...' header.")
    return authorization[7:].strip()


def get_registry(request: Request) -> ProviderRegistry:
    return request.app.state.registry


async def current_merchant(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Merchant:
    """Dashboard auth (JWT from /auth/login)."""
    token = _bearer(authorization)
    try:
        merchant_id = decode_access_token(token, settings.jwt_secret)
    except (jwt.PyJWTError, ValueError):
        raise ApiError(401, "unauthorized", "Invalid or expired token.")
    merchant = await session.get(Merchant, merchant_id)
    if merchant is None or merchant.status != "active":
        raise ApiError(401, "unauthorized", "Account not found or not active.")
    return merchant


@dataclass
class ApiCaller:
    merchant: Merchant
    key: ApiKey
    mode: str


async def api_caller(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ApiCaller:
    """Merchant API auth (secret key sk_test_... / sk_live_...). The key decides the mode."""
    token = _bearer(authorization)
    if not token.startswith(("sk_test_", "sk_live_")):
        raise ApiError(401, "unauthorized", "Use a secret API key (sk_test_... or sk_live_...).")
    key = (
        await session.execute(
            select(ApiKey).where(ApiKey.prefix == token[:KEY_PREFIX_LEN], ApiKey.revoked_at.is_(None))
        )
    ).scalar_one_or_none()
    if key is None or not hmac.compare_digest(key.key_hash, hash_api_key(token)):
        raise ApiError(401, "unauthorized", "Invalid API key.")
    merchant = await session.get(Merchant, key.merchant_id)
    if merchant is None or merchant.status != "active":
        raise ApiError(403, "account_suspended", "This account is not active.")
    if key.mode == "live" and not merchant.live_enabled:
        raise ApiError(403, "live_not_enabled", "Live mode is not enabled for this account yet.")
    now = datetime.now(timezone.utc)
    if key.last_used_at is None or now - key.last_used_at > timedelta(minutes=1):
        key.last_used_at = now
        await session.commit()
    return ApiCaller(merchant=merchant, key=key, mode=key.mode)


def require_internal_secret(
    x_internal_secret: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.internal_tick_secret:
        raise ApiError(503, "not_configured", "INTERNAL_TICK_SECRET is not configured.")
    if not x_internal_secret or not hmac.compare_digest(x_internal_secret, settings.internal_tick_secret):
        raise ApiError(401, "unauthorized", "Bad internal secret.")


@dataclass
class AppCaller:
    app: App
    merchant: Merchant
    mode: str


async def app_caller(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AppCaller:
    """Campay-style auth: `Authorization: Token <token>` where the token comes from POST /api/token/."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() not in ("token", "bearer") or not token.strip():
        raise ApiError(401, "unauthorized", "Send the header 'Authorization: Token <token>' (get a token with POST /api/token/).")
    try:
        app_id = decode_app_token(token.strip(), settings.jwt_secret)
    except (jwt.PyJWTError, ValueError):
        raise ApiError(401, "unauthorized", "Invalid or expired token. Request a new one with POST /api/token/.")
    app = await session.get(App, app_id)
    if app is None or app.revoked_at is not None:
        raise ApiError(401, "unauthorized", "This app does not exist or was revoked.")
    merchant = await session.get(Merchant, app.merchant_id)
    if merchant is None or merchant.status != "active":
        raise ApiError(403, "account_suspended", "This account is not active.")
    if app.mode == "live" and not merchant.live_enabled:
        raise ApiError(403, "live_not_enabled", "Live mode is not enabled for this account yet.")
    now = datetime.now(timezone.utc)
    if app.last_used_at is None or now - app.last_used_at > timedelta(minutes=1):
        app.last_used_at = now
        await session.commit()
    return AppCaller(app=app, merchant=merchant, mode=app.mode)
