"""Merchant API (secret key auth). The key's mode (test/live) decides everything."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ApiCaller, api_caller, get_registry
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Account, CheckoutSession
from app.providers.registry import ProviderRegistry
from app.services import checkout as checkout_service
from app.services import transactions as tx_service
from app.services.jobs import run_deliveries, start_watch
from app.services.serializers import session_to_dict, tx_to_dict
from app.errors import ApiError

router = APIRouter(prefix="/v1", tags=["merchant api"])


class TransferIn(BaseModel):
    amount: int = Field(gt=0, le=10_000_000)
    phone: str = Field(min_length=9, max_length=20)
    description: str | None = Field(default=None, max_length=160)
    merchant_reference: str | None = Field(default=None, max_length=100)
    metadata: dict | None = None


class CheckoutSessionIn(BaseModel):
    amount: int = Field(gt=0, le=10_000_000)
    description: str | None = Field(default=None, max_length=160)
    merchant_reference: str | None = Field(default=None, max_length=100)
    redirect_url: str | None = Field(default=None, max_length=500)
    expires_in_minutes: int = Field(default=60, ge=1, le=1440)
    metadata: dict | None = None


def _check_metadata(metadata: dict | None) -> dict | None:
    if metadata is not None and len(str(metadata)) > 2000:
        raise ApiError(422, "metadata_too_large", "metadata must stay under 2000 characters.")
    return metadata


@router.post("/collections", status_code=201)
async def create_collection(
    body: TransferIn,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    idempotency_key: str | None = Header(default=None),
    caller: ApiCaller = Depends(api_caller),
    session: AsyncSession = Depends(get_session),
    registry: ProviderRegistry = Depends(get_registry),
):
    tx, created = await tx_service.create_collection(
        session, registry,
        merchant=caller.merchant, mode=caller.mode, amount=body.amount, phone=body.phone,
        description=body.description, merchant_reference=body.merchant_reference,
        idempotency_key=idempotency_key, user_metadata=_check_metadata(body.metadata),
    )
    if not created:
        response.status_code = 200
    elif tx.status in ("created", "pending"):
        start_watch(request.app.state, tx)
    background.add_task(run_deliveries, request.app.state)
    return tx_to_dict(tx)


@router.get("/collections/{public_id}")
async def get_collection(
    public_id: str,
    caller: ApiCaller = Depends(api_caller),
    session: AsyncSession = Depends(get_session),
    registry: ProviderRegistry = Depends(get_registry),
):
    tx = await tx_service.get_by_public_id(session, caller.merchant.id, caller.mode, public_id, "collection")
    return tx_to_dict(await tx_service.refresh_if_pending(session, registry, tx))


@router.post("/payouts", status_code=201)
async def create_payout(
    body: TransferIn,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    idempotency_key: str | None = Header(default=None),
    caller: ApiCaller = Depends(api_caller),
    session: AsyncSession = Depends(get_session),
    registry: ProviderRegistry = Depends(get_registry),
):
    tx, created = await tx_service.create_payout(
        session, registry,
        merchant=caller.merchant, mode=caller.mode, amount=body.amount, phone=body.phone,
        description=body.description, merchant_reference=body.merchant_reference,
        idempotency_key=idempotency_key, user_metadata=_check_metadata(body.metadata),
    )
    if not created:
        response.status_code = 200
    elif tx.status in ("created", "pending"):
        start_watch(request.app.state, tx)
    background.add_task(run_deliveries, request.app.state)
    return tx_to_dict(tx)


@router.get("/payouts/{public_id}")
async def get_payout(
    public_id: str,
    caller: ApiCaller = Depends(api_caller),
    session: AsyncSession = Depends(get_session),
    registry: ProviderRegistry = Depends(get_registry),
):
    tx = await tx_service.get_by_public_id(session, caller.merchant.id, caller.mode, public_id, "payout")
    return tx_to_dict(await tx_service.refresh_if_pending(session, registry, tx))


@router.get("/balance")
async def balance(caller: ApiCaller = Depends(api_caller), session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(Account).where(Account.merchant_id == caller.merchant.id, Account.mode == caller.mode).execution_options(populate_existing=True)
        )
    ).scalars().all()
    out = {"mode": caller.mode, "currency": "XAF", "available": 0, "held": 0}
    for acct in rows:
        out["available" if acct.type == "merchant_available" else "held"] = acct.balance
    return out


@router.get("/transactions")
async def transactions(
    type: str | None = Query(None, pattern="^(collection|payout)$"),
    status: str | None = Query(None, pattern="^(pending|succeeded|failed|expired)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    caller: ApiCaller = Depends(api_caller),
    session: AsyncSession = Depends(get_session),
    registry: ProviderRegistry = Depends(get_registry),
):
    rows = await tx_service.list_transactions(session, caller.merchant.id, caller.mode, type_=type, status=status, limit=limit, offset=offset)
    await tx_service.refresh_many(session, registry, rows)
    return {"data": [tx_to_dict(tx) for tx in rows], "limit": limit, "offset": offset}


@router.post("/checkout-sessions", status_code=201)
async def create_checkout_session(
    body: CheckoutSessionIn,
    caller: ApiCaller = Depends(api_caller),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    cs = await checkout_service.create_session(
        session, merchant=caller.merchant, mode=caller.mode, amount=body.amount, description=body.description,
        merchant_reference=body.merchant_reference, redirect_url=body.redirect_url,
        expires_in_minutes=body.expires_in_minutes, user_metadata=_check_metadata(body.metadata),
    )
    return session_to_dict(cs, settings.gate_url)


@router.get("/checkout-sessions/{public_id}")
async def get_checkout_session(
    public_id: str,
    caller: ApiCaller = Depends(api_caller),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    cs = (
        await session.execute(
            select(CheckoutSession).where(
                CheckoutSession.public_id == public_id,
                CheckoutSession.merchant_id == caller.merchant.id,
                CheckoutSession.mode == caller.mode,
            ).execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if cs is None:
        raise ApiError(404, "not_found", "Checkout session not found.")
    data = session_to_dict(cs, settings.gate_url)
    data["status"] = checkout_service.effective_status(cs)
    return data
