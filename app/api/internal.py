"""Operational endpoints for the external pinger and for you. All need X-Internal-Secret."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_registry, require_internal_secret
from app.db import get_session
from app.errors import ApiError
from app.providers.base import ProviderError
from app.providers.registry import ProviderRegistry
from app.services.jobs import record_balance_reconciliation
from app.services.transactions import expire_stale, reconcile_pending
from app.services.webhooks_out import deliver_due

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal_secret)])


@router.get("/db-check")
async def db_check(session: AsyncSession = Depends(get_session)) -> dict:
    """Confirms Neon connectivity, that both migrations are applied, and that platform accounts are seeded."""
    await session.execute(text("SELECT 1"))
    rows = (await session.execute(text("SELECT mode, type FROM accounts WHERE merchant_id IS NULL ORDER BY mode, type"))).all()
    has_checkout = (await session.execute(text("SELECT to_regclass('public.checkout_sessions') IS NOT NULL"))).scalar_one()
    return {
        "db": "ok",
        "platform_accounts": [f"{mode}:{type_}" for mode, type_ in rows],
        "platform_accounts_seeded": len(rows) == 4,
        "migration_002_applied": bool(has_checkout),
    }


@router.get("/provider-check")
async def provider_check(mode: str = Query("live", pattern="^(test|live)$"), registry: ProviderRegistry = Depends(get_registry)) -> dict:
    """Confirms provider credentials work by reading the provider balance."""
    try:
        provider = registry.for_mode(mode)
        balance = await provider.get_balance()
    except ProviderError as exc:
        raise ApiError(502, "provider_error", f"{type(exc).__name__}: {exc}") from exc
    return {"mode": mode, "provider": provider.name, "total": balance.total, "mtn": balance.mtn, "orange": balance.orange, "currency": balance.currency}


@router.api_route("/tick", methods=["GET", "POST"])
async def tick(request: Request, session: AsyncSession = Depends(get_session), registry: ProviderRegistry = Depends(get_registry)) -> dict:
    """Run every 5-10 minutes by the external pinger: deliver due webhooks, re-check pending
    transactions with the provider, expire stale items, occasionally reconcile balances."""
    deliveries = await deliver_due(session, request.app.state.http)
    reconciled = await reconcile_pending(session, registry)
    expired = await expire_stale(session)
    balance = await record_balance_reconciliation(session, registry)
    return {"deliveries": deliveries, "reconciled": reconciled, "expired": expired, "balance_check": balance}
