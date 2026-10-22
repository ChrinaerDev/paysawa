"""Dashboard (JWT) endpoints to create and manage Campay-style apps and to reveal their credentials."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_merchant
from app.config import Settings, get_settings
from app.db import get_session
from app.models import App, Merchant
from app.services import apps as apps_service
from app.services.serializers import iso

router = APIRouter(tags=["Apps"])


class AppIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    mode: str = Field(pattern="^(test|live)$")
    webhook_url: str | None = Field(default=None, max_length=500)


class AppPatch(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    webhook_url: str | None = Field(default=None, max_length=500)  # "" removes it


def app_to_dict(app: App, settings: Settings) -> dict:
    return {
        "id": str(app.id), "name": app.name, "mode": app.mode, "username": app.username, "webhook_url": app.webhook_url,
        "api_base_url": f"{settings.app_base_url.rstrip('/')}/api/",
        "revealable": apps_service.revealable(app, settings),
        "revoked_at": iso(app.revoked_at), "last_used_at": iso(app.last_used_at), "created_at": iso(app.created_at),
    }


@router.post("/me/apps", status_code=201)
async def create_app(body: AppIn, merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    app = await apps_service.create_app(session, merchant, name=body.name, mode=body.mode, webhook_url=body.webhook_url, settings=settings)
    return app_to_dict(app, settings)


@router.get("/me/apps")
async def list_apps(merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    rows = (await session.execute(select(App).where(App.merchant_id == merchant.id).order_by(App.created_at.desc()))).scalars().all()
    return {"data": [app_to_dict(a, settings) for a in rows]}


@router.get("/me/apps/{app_id}/credentials")
async def app_credentials(app_id: uuid.UUID, merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    """Show/hide toggle backend: username, password and webhook key of the app, any time."""
    app = await apps_service.get_owned(session, merchant, app_id)
    return apps_service.credentials(app, settings)


@router.patch("/me/apps/{app_id}")
async def update_app(app_id: uuid.UUID, body: AppPatch, merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    app = await apps_service.get_owned(session, merchant, app_id)
    app = await apps_service.update_app(session, app, name=body.name, webhook_url=body.webhook_url, settings=settings)
    return app_to_dict(app, settings)


@router.delete("/me/apps/{app_id}")
async def revoke_app(app_id: uuid.UUID, merchant: Merchant = Depends(current_merchant), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    app = await apps_service.get_owned(session, merchant, app_id)
    return app_to_dict(await apps_service.revoke_app(session, app), settings)
