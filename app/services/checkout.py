"""Hosted checkout sessions: merchant creates a session, the customer pays on the pay page."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError
from app.fees import MIN_AMOUNT
from app.models import CheckoutSession, Merchant, Transaction
from app.netsafety import UnsafeUrl, check_public_url
from app.providers.registry import ProviderRegistry
from app.security import new_public_id
from app.services.transactions import create_collection

MAX_ATTEMPTS = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_session(
    session: AsyncSession,
    *,
    merchant: Merchant,
    mode: str,
    amount: int,
    description: str | None,
    merchant_reference: str | None,
    redirect_url: str | None,
    expires_in_minutes: int,
    user_metadata: dict | None,
) -> CheckoutSession:
    if merchant.status != "active":
        raise ApiError(403, "account_suspended", "This account cannot create checkout sessions.")
    if mode == "live" and not merchant.live_enabled:
        raise ApiError(403, "live_not_enabled", "Live mode is not enabled for this account yet.")
    if amount < MIN_AMOUNT:
        raise ApiError(422, "amount_too_small", f"The minimum amount is {MIN_AMOUNT} XAF.")
    if redirect_url:
        try:
            await asyncio.to_thread(
                check_public_url, redirect_url, allow_http=mode == "test",
                allow_private=mode == "test" and get_settings().allow_private_webhook_urls,
            )
        except UnsafeUrl as exc:
            raise ApiError(422, "invalid_redirect_url", str(exc)) from exc
    cs = CheckoutSession(
        public_id=new_public_id("cs"),
        merchant_id=merchant.id,
        mode=mode,
        amount=amount,
        description=description,
        merchant_reference=merchant_reference,
        redirect_url=redirect_url,
        meta={"user": user_metadata or {}},
        expires_at=_now() + timedelta(minutes=max(5, min(expires_in_minutes, 24 * 60))),
    )
    session.add(cs)
    await session.commit()
    return cs


async def get_public(session: AsyncSession, public_id: str, *, lock: bool = False) -> CheckoutSession:
    stmt = select(CheckoutSession).where(CheckoutSession.public_id == public_id).execution_options(populate_existing=True)
    if lock:
        stmt = stmt.with_for_update()
    cs = (await session.execute(stmt)).scalar_one_or_none()
    if cs is None:
        raise ApiError(404, "not_found", "Checkout session not found.")
    return cs


def effective_status(cs: CheckoutSession) -> str:
    if cs.status == "open" and cs.expires_at < _now():
        return "expired"
    return cs.status


async def pay(session: AsyncSession, registry: ProviderRegistry, public_id: str, phone: str) -> tuple[CheckoutSession, Transaction]:
    cs = await get_public(session, public_id, lock=True)
    state = effective_status(cs)
    if state == "paid":
        await session.rollback()
        raise ApiError(409, "already_paid", "This checkout session is already paid.")
    if state == "expired":
        cs.status = "expired"
        await session.commit()
        raise ApiError(410, "session_expired", "This checkout session has expired.")
    if cs.attempts >= MAX_ATTEMPTS:
        await session.rollback()
        raise ApiError(429, "too_many_attempts", "Too many payment attempts for this session.")
    if cs.transaction_id:
        last = await session.get(Transaction, cs.transaction_id)
        if last is not None and last.status in ("created", "pending"):
            await session.rollback()
            raise ApiError(409, "payment_in_progress", "A payment is already in progress. Approve it on your phone.")
    merchant = await session.get(Merchant, cs.merchant_id)
    cs.attempts += 1
    await session.commit()  # releases the lock before talking to the provider

    tx, _ = await create_collection(
        session,
        registry,
        merchant=merchant,
        mode=cs.mode,
        amount=cs.amount,
        phone=phone,
        description=cs.description,
        merchant_reference=cs.merchant_reference,
        idempotency_key=None,
        user_metadata=(cs.meta or {}).get("user"),
        internal={"checkout_session": cs.public_id},
    )
    cs = await get_public(session, public_id, lock=True)
    if cs.status == "open":
        cs.transaction_id = tx.id
    await session.commit()
    return cs, tx
