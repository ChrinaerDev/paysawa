"""Dashboard API (JWT): signup/login, profile, API keys, webhook endpoints, balances, history."""
from __future__ import annotations

import asyncio
import hmac
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_merchant, get_registry
from app.config import Settings, get_settings
from app.db import get_session
from app.errors import ApiError
from app.models import Account, ApiKey, Merchant, WebhookDelivery, WebhookEndpoint
from app.netsafety import UnsafeUrl, check_public_url
from app.ratelimit import RateLimiter, client_ip
from app.security import create_access_token, derive_api_key, hash_api_key, new_webhook_secret, verify_password
from app.services import merchants as merchant_service
from app.services.serializers import iso, tx_to_dict
from app.providers.registry import ProviderRegistry
from app.services.transactions import list_transactions, refresh_many
from app.services.webhooks_out import EVENT_TYPES

router = APIRouter(tags=["dashboard"])
_login_limiter = RateLimiter(10, 300)
_signup_limiter = RateLimiter(5, 3600)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    email: str
    password: str


class ApiKeyIn(BaseModel):
    mode: str = Field(pattern="^(test|live)$")
    label: str | None = Field(default=None, max_length=60)


class WebhookEndpointIn(BaseModel):
    mode: str = Field(pattern="^(test|live)$")
    url: str = Field(max_length=500)
    events: list[str] = []


def merchant_to_dict(m: Merchant) -> dict:
    return {
        "id": str(m.id),
        "name": m.name,
        "email": m.email,
        "status": m.status,
        "live_enabled": m.live_enabled,
        "limits": {"per_transaction": m.per_txn_limit, "daily": m.daily_limit},
        "fees_bps": {"collection": m.collection_fee_bps, "payout": m.payout_fee_bps},
        "created_at": iso(m.created_at),
    }


@router.post("/auth/signup", status_code=201)
async def signup(body: SignupIn, request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    if not settings.allow_signup:
        raise ApiError(403, "signup_disabled", "Signup is disabled.")
    _signup_limiter.check(client_ip(request))
    if not _EMAIL.match(body.email):
        raise ApiError(422, "invalid_email", "Invalid email address.")
    merchant = await merchant_service.create_merchant(session, name=body.name, email=body.email, password=body.password)
    token = create_access_token(merchant.id, settings.jwt_secret)
    return {"token": token, "merchant": merchant_to_dict(merchant)}


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    _login_limiter.check(f"{client_ip(request)}:{body.email.lower()}")
    merchant = await merchant_service.get_by_email(session, body.email)
    ok = merchant is not None and await asyncio.to_thread(verify_password, body.password, merchant.password_hash)
    if not ok or merchant.status != "active":
        raise ApiError(401, "invalid_credentials", "Wrong email or password.")
    return {"token": create_access_token(merchant.id, settings.jwt_secret), "merchant": merchant_to_dict(merchant)}


@router.get("/me")
async def me(merchant: Merchant = Depends(current_merchant)):
    return merchant_to_dict(merchant)


@router.get("/me/balance")
async def my_balance(merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Account).where(Account.merchant_id == merchant.id).execution_options(populate_existing=True))).scalars().all()
    out: dict = {"currency": "XAF", "test": {"available": 0, "held": 0}, "live": {"available": 0, "held": 0}}
    for acct in rows:
        out[acct.mode]["available" if acct.type == "merchant_available" else "held"] = acct.balance
    return out


@router.get("/me/transactions")
async def my_transactions(
    mode: str = Query("test", pattern="^(test|live)$"),
    type: str | None = Query(None, pattern="^(collection|payout)$"),
    status: str | None = Query(None, pattern="^(pending|succeeded|failed|expired)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    merchant: Merchant = Depends(current_merchant),
    session: AsyncSession = Depends(get_session),
    registry: ProviderRegistry = Depends(get_registry),
):
    rows = await list_transactions(session, merchant.id, mode, type_=type, status=status, limit=limit, offset=offset)
    await refresh_many(session, registry, rows)
    return {"data": [tx_to_dict(tx) for tx in rows], "limit": limit, "offset": offset}


# ------------------------------------------------------------------ API keys
def _derived_secret(k: ApiKey, secret: str) -> str | None:
    """The key's full secret if it can be re-derived (keys created with the revealable scheme), else None."""
    if not secret:
        return None
    full = derive_api_key(k.mode, k.id, secret)
    return full if hmac.compare_digest(hash_api_key(full), k.key_hash) else None


def _key_to_dict(k: ApiKey, settings: Settings) -> dict:
    return {
        "id": str(k.id), "mode": k.mode, "label": k.label, "prefix": k.prefix,
        "revealable": k.revoked_at is None and _derived_secret(k, settings.key_secret) is not None,
        "last_used_at": iso(k.last_used_at), "revoked_at": iso(k.revoked_at), "created_at": iso(k.created_at),
    }


@router.post("/me/api-keys", status_code=201)
async def create_api_key(body: ApiKeyIn, merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    key, secret = await merchant_service.issue_api_key(session, merchant, body.mode, body.label, settings.key_secret)
    return {**_key_to_dict(key, settings), "secret": secret}


@router.get("/me/api-keys")
async def list_api_keys(merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    keys = (await session.execute(select(ApiKey).where(ApiKey.merchant_id == merchant.id).order_by(ApiKey.created_at.desc()))).scalars().all()
    return {"data": [_key_to_dict(k, settings) for k in keys]}


@router.get("/me/api-keys/{key_id}/secret")
async def reveal_api_key(key_id: uuid.UUID, merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    """Show/hide toggle backend: returns the full secret of a key (test or live) at any time."""
    key = (await session.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.merchant_id == merchant.id))).scalar_one_or_none()
    if key is None or key.revoked_at is not None:
        raise ApiError(404, "not_found", "API key not found or revoked.")
    full = _derived_secret(key, settings.key_secret)
    if full is None:
        raise ApiError(409, "not_revealable", "This key cannot be revealed (created before reveal support, or API_KEY_SECRET changed). Create a new key.")
    return {"id": str(key.id), "mode": key.mode, "secret": full}


@router.delete("/me/api-keys/{key_id}")
async def revoke_api_key(key_id: uuid.UUID, merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    key = (await session.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.merchant_id == merchant.id))).scalar_one_or_none()
    if key is None:
        raise ApiError(404, "not_found", "API key not found.")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        await session.commit()
    return _key_to_dict(key, settings)


# ------------------------------------------------------------------ webhook endpoints
def _endpoint_to_dict(e: WebhookEndpoint, *, with_secret: bool = False) -> dict:
    data = {"id": str(e.id), "mode": e.mode, "url": e.url, "events": e.events or [], "is_active": e.is_active, "created_at": iso(e.created_at)}
    if with_secret:
        data["signing_secret"] = e.signing_secret
    return data


@router.post("/me/webhook-endpoints", status_code=201)
async def create_webhook_endpoint(body: WebhookEndpointIn, merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    unknown = [e for e in body.events if e not in EVENT_TYPES]
    if unknown:
        raise ApiError(422, "invalid_events", f"Unknown events: {unknown}. Valid: {list(EVENT_TYPES)}")
    try:
        await asyncio.to_thread(
            check_public_url, body.url, allow_http=body.mode == "test",
            allow_private=body.mode == "test" and settings.allow_private_webhook_urls,
        )
    except UnsafeUrl as exc:
        raise ApiError(422, "invalid_url", str(exc)) from exc
    endpoint = WebhookEndpoint(id=uuid.uuid4(), merchant_id=merchant.id, mode=body.mode, url=body.url, signing_secret=new_webhook_secret(), events=body.events)
    session.add(endpoint)
    await session.commit()
    return _endpoint_to_dict(endpoint, with_secret=True)


@router.get("/me/webhook-endpoints/{endpoint_id}/secret")
async def reveal_webhook_secret(endpoint_id: uuid.UUID, merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session)):
    endpoint = (await session.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id, WebhookEndpoint.merchant_id == merchant.id, WebhookEndpoint.style == "paysawa"))).scalar_one_or_none()
    if endpoint is None:
        raise ApiError(404, "not_found", "Webhook endpoint not found.")
    return {"id": str(endpoint.id), "signing_secret": endpoint.signing_secret}


@router.get("/me/webhook-endpoints")
async def list_webhook_endpoints(merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(WebhookEndpoint).where(WebhookEndpoint.merchant_id == merchant.id, WebhookEndpoint.style == "paysawa").order_by(WebhookEndpoint.created_at.desc()))).scalars().all()
    return {"data": [_endpoint_to_dict(e) for e in rows]}


@router.delete("/me/webhook-endpoints/{endpoint_id}")
async def delete_webhook_endpoint(endpoint_id: uuid.UUID, merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session)):
    endpoint = (await session.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id, WebhookEndpoint.merchant_id == merchant.id, WebhookEndpoint.style == "paysawa"))).scalar_one_or_none()
    if endpoint is None:
        raise ApiError(404, "not_found", "Webhook endpoint not found.")
    await session.delete(endpoint)
    await session.commit()
    return {"deleted": True}


@router.get("/me/webhook-deliveries")
async def list_webhook_deliveries(limit: int = Query(50, ge=1, le=100), merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(WebhookDelivery)
            .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
            .where(WebhookEndpoint.merchant_id == merchant.id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return {
        "data": [
            {"id": d.id, "endpoint_id": str(d.endpoint_id), "event": d.event_type, "status": d.status, "attempts": d.attempts,
             "last_status_code": d.last_status_code, "last_error": d.last_error, "next_attempt_at": iso(d.next_attempt_at),
             "created_at": iso(d.created_at), "delivered_at": iso(d.delivered_at)}
            for d in rows
        ]
    }
