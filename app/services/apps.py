"""Campay-style apps: creation, credentials (revealable), webhook URL, revocation."""
from __future__ import annotations

import asyncio
import hmac
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ApiError
from app.models import App, Merchant, WebhookEndpoint
from app.netsafety import UnsafeUrl, check_public_url
from app.security import derive_app_password, derive_app_webhook_key, hash_api_key, new_app_username


async def _validate_url(url: str, mode: str, settings: Settings) -> None:
    try:
        await asyncio.to_thread(
            check_public_url, url, allow_http=mode == "test",
            allow_private=mode == "test" and settings.allow_private_webhook_urls,
        )
    except UnsafeUrl as exc:
        raise ApiError(422, "invalid_url", str(exc)) from exc


async def _sync_endpoint(session: AsyncSession, app: App, url: str | None) -> None:
    """Keeps one hidden Campay-style webhook endpoint in step with the app's webhook URL."""
    endpoint = (await session.execute(select(WebhookEndpoint).where(WebhookEndpoint.app_id == app.id))).scalar_one_or_none()
    if not url:
        if endpoint is not None:
            endpoint.is_active = False
        return
    if endpoint is None:
        session.add(WebhookEndpoint(
            id=uuid.uuid4(), merchant_id=app.merchant_id, mode=app.mode, url=url, signing_secret="",
            events=[], style="campay", app_id=app.id,
        ))
    else:
        endpoint.url = url
        endpoint.is_active = True


async def create_app(session: AsyncSession, merchant: Merchant, *, name: str, mode: str, webhook_url: str | None, settings: Settings) -> App:
    if not settings.key_secret:
        raise ApiError(500, "not_configured", "Set API_KEY_SECRET (or JWT_SECRET) in .env before creating apps.")
    name = name.strip()
    if not name:
        raise ApiError(422, "invalid_name", "Give the app a name.")
    if webhook_url:
        await _validate_url(webhook_url, mode, settings)
    app_id = uuid.uuid4()
    app = App(
        id=app_id, merchant_id=merchant.id, mode=mode, name=name, username=new_app_username(),
        password_hash=hash_api_key(derive_app_password(app_id, settings.key_secret)), webhook_url=webhook_url or None,
    )
    session.add(app)
    await session.flush()
    await _sync_endpoint(session, app, webhook_url or None)
    await session.commit()
    return app


async def update_app(session: AsyncSession, app: App, *, name: str | None, webhook_url: str | None, settings: Settings) -> App:
    """webhook_url: None = leave unchanged, "" = remove, otherwise set."""
    if name is not None and name.strip():
        app.name = name.strip()
    if webhook_url is not None:
        if webhook_url:
            await _validate_url(webhook_url, app.mode, settings)
        app.webhook_url = webhook_url or None
        await _sync_endpoint(session, app, webhook_url or None)
    await session.commit()
    return app


async def revoke_app(session: AsyncSession, app: App) -> App:
    if app.revoked_at is None:
        app.revoked_at = datetime.now(timezone.utc)
        await _sync_endpoint(session, app, None)
        await session.commit()
    return app


async def get_owned(session: AsyncSession, merchant: Merchant, app_id: uuid.UUID) -> App:
    app = (await session.execute(select(App).where(App.id == app_id, App.merchant_id == merchant.id))).scalar_one_or_none()
    if app is None:
        raise ApiError(404, "not_found", "App not found.")
    return app


def revealable(app: App, settings: Settings) -> bool:
    if app.revoked_at is not None or not settings.key_secret:
        return False
    return hmac.compare_digest(hash_api_key(derive_app_password(app.id, settings.key_secret)), app.password_hash)


def credentials(app: App, settings: Settings) -> dict:
    if not revealable(app, settings):
        raise ApiError(409, "not_revealable", "These credentials cannot be revealed (revoked app, or API_KEY_SECRET changed). Create a new app.")
    return {
        "username": app.username,
        "password": derive_app_password(app.id, settings.key_secret),
        "webhook_key": derive_app_webhook_key(app.id, settings.key_secret),
        "api_base_url": f"{settings.app_base_url.rstrip('/')}/api/",
    }
