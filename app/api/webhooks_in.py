"""Inbound provider webhooks. A webhook is only a hint: we verify the signature, store it,
then RE-FETCH the transaction from the provider before touching any balance."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_registry
from app.db import get_session
from app.errors import ApiError
from app.models import ProviderEvent, Transaction
from app.providers.base import ProviderError
from app.providers.registry import ProviderRegistry
from app.services.jobs import run_deliveries
from app.services.transactions import sync_with_provider

router = APIRouter(tags=["provider webhooks"])
logger = logging.getLogger("paysawa.inbound")


async def _params(request: Request) -> dict[str, str]:
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                params.update({k: str(v) for k, v in body.items()})
        except ValueError:
            try:
                form = await request.form()
                params.update({k: str(v) for k, v in form.items()})
            except Exception:
                pass
    return params


@router.api_route("/webhooks/campay", methods=["GET", "POST"])
async def campay_webhook(
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    registry: ProviderRegistry = Depends(get_registry),
):
    params = await _params(request)
    event = None
    for _mode, provider in registry.campay_verifiers():
        try:
            event = provider.verify_webhook(params)
            break
        except ProviderError:
            continue
    if event is None:
        raise ApiError(401, "invalid_signature", "Webhook signature could not be verified.")

    stmt = (
        pg_insert(ProviderEvent)
        .values(provider="campay", dedupe_key=f"{event.reference}:{event.status.value}", payload=event.raw, signature_valid=True)
        .on_conflict_do_nothing(index_elements=["provider", "dedupe_key"])
        .returning(ProviderEvent.id)
    )
    event_id = (await session.execute(stmt)).scalar_one_or_none()
    await session.commit()
    if event_id is None:
        return {"status": "duplicate"}

    tx = None
    if event.external_reference:
        try:
            tx = (await session.execute(select(Transaction).where(Transaction.id == uuid.UUID(event.external_reference)))).scalar_one_or_none()
        except ValueError:
            tx = None
    if tx is None:
        tx = (
            await session.execute(select(Transaction).where(Transaction.provider == "campay", Transaction.provider_reference == event.reference))
        ).scalar_one_or_none()

    error = None
    if tx is None:
        error = "unknown transaction"
        logger.warning("campay webhook for unknown transaction reference=%s", event.reference)
    else:
        if not tx.provider_reference:  # collect() timed out earlier: the webhook tells us the reference
            tx.provider_reference = event.reference
            await session.commit()
    await _finish(session, registry, event_id, tx, error)
    background.add_task(run_deliveries, request.app.state)
    return {"status": "accepted"}


async def _finish(session: AsyncSession, registry: ProviderRegistry, event_id: int, tx, error: str | None) -> None:
    if tx is not None:
        try:
            await sync_with_provider(session, registry, tx.id)  # re-fetch + settle; never raises provider errors
        except Exception:
            logger.exception("settling from webhook failed tx=%s", tx.public_id)
            error = "settle failed"
            await session.rollback()
    row = await session.get(ProviderEvent, event_id)
    if row is not None:
        row.processed_at = datetime.now(timezone.utc)
        row.error = error
        await session.commit()
