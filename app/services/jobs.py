"""Work that runs after a response (BackgroundTasks) or from /internal/tick."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import get_sessionmaker
from app.models import Account, ReconciliationRun
from app.providers.base import ProviderError
from app.providers.registry import ProviderNotConfigured
from app.services.webhooks_out import deliver_due

logger = logging.getLogger("paysawa.jobs")


async def run_deliveries(app_state) -> None:
    """Best-effort immediate webhook delivery so merchants do not wait for the next tick."""
    try:
        async with get_sessionmaker()() as session:
            await deliver_due(session, app_state.http)
    except Exception:  # never let a background task crash the worker
        logger.exception("background webhook delivery failed")


async def record_balance_reconciliation(session, registry, min_interval_hours: int = 6) -> dict:
    """Compares our live ledger with the real Campay balance. Expect a constant non-zero diff
    equal to any money that was in the Campay account before the gateway started."""
    last = (await session.execute(select(func.max(ReconciliationRun.ran_at)))).scalar_one()
    if last and datetime.now(timezone.utc) - last < timedelta(hours=min_interval_hours):
        return {"skipped": "recent run exists"}
    try:
        balance = await registry.for_mode("live").get_balance()
    except (ProviderNotConfigured, ProviderError) as exc:
        return {"skipped": f"provider unavailable: {type(exc).__name__}"}
    float_balance = (
        await session.execute(
            select(Account.balance).where(Account.merchant_id.is_(None), Account.mode == "live", Account.type == "provider_float")
        )
    ).scalar_one_or_none()
    if float_balance is None:
        return {"skipped": "platform accounts not seeded"}
    run = ReconciliationRun(ledger_total=-float_balance, provider_balance=balance.total)
    session.add(run)
    await session.commit()
    return {"ledger_total": -float_balance, "provider_balance": balance.total, "diff": balance.total + float_balance}
