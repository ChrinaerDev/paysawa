"""Work that runs after a response (BackgroundTasks) or from /internal/tick."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import get_sessionmaker
from app.models import Account, ReconciliationRun, Transaction
from app.providers.base import ProviderError
from app.providers.registry import ProviderNotConfigured
from app.services.transactions import TERMINAL, sync_with_provider
from app.services.webhooks_out import deliver_due

logger = logging.getLogger("paysawa.jobs")


async def run_deliveries(app_state) -> None:
    """Best-effort immediate webhook delivery so merchants do not wait for the next tick."""
    try:
        async with get_sessionmaker()() as session:
            await deliver_due(session, app_state.http)
    except Exception:  # never let a background task crash the worker
        logger.exception("background webhook delivery failed")


async def watch_pending(app_state, tx_id, *, max_seconds: int = 300) -> None:
    """Polls the provider for ONE pending transaction (every 3 s for a minute, then every 10 s) until it is final
    or the time is up. Only touches the database while a transaction is actually pending, so Neon can still sleep.
    After that, the Campay webhook or /internal/tick remain as safety nets."""
    started = time.monotonic()
    while time.monotonic() - started < max_seconds:
        await asyncio.sleep(3 if time.monotonic() - started < 60 else 10)
        try:
            async with get_sessionmaker()() as session:
                await sync_with_provider(session, app_state.registry, tx_id)
                tx = await session.get(Transaction, tx_id, populate_existing=True)
                if tx is None or tx.status in TERMINAL:
                    break
        except Exception:
            logger.exception("watcher error for %s", tx_id)
    await run_deliveries(app_state)


def start_watch(app_state, tx) -> None:
    """Fire-and-forget watcher for a freshly created live transaction that is still pending."""
    if tx.status not in ("created", "pending") or not tx.provider_reference or tx.provider == "simulated":
        return
    watchers = getattr(app_state, "watchers", None)
    if watchers is None:
        watchers = app_state.watchers = set()
    task = asyncio.create_task(watch_pending(app_state, tx.id))
    watchers.add(task)
    task.add_done_callback(watchers.discard)


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
