"""Collections and payouts: creation, provider execution, settlement, reconciliation.

Rules that matter for money:
  * the transaction row is COMMITTED before any provider call (a crash leaves a trace);
  * ProviderRejected / ProviderAuthError  -> definite failure, safe to fail (and release holds);
  * ProviderUnavailable                   -> outcome UNKNOWN, never fail; reconcile later;
  * every ledger posting is idempotent and state changes happen under a row lock.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.fees import MIN_AMOUNT, compute_fee
from app.models import CheckoutSession, Merchant, Transaction
from app.phone import normalize_phone
from app.providers.base import (
    CollectRequest,
    InvalidPhoneNumber,
    PayoutRequest,
    ProviderAuthError,
    ProviderError,
    ProviderRejected,
    ProviderStatus,
    ProviderUnavailable,
)
from app.providers.registry import ProviderNotConfigured, ProviderRegistry
from app.security import new_public_id
from app.services import ledger
from app.services.webhooks_out import enqueue_event

logger = logging.getLogger("paysawa.tx")

TERMINAL = ("succeeded", "failed", "expired")
GENERIC_REJECTED = "The payment provider rejected this request."
GENERIC_UNAVAILABLE = "The payment provider is temporarily unavailable."


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ validation
def _check_can_transact(merchant: Merchant, mode: str) -> None:
    if merchant.status != "active":
        raise ApiError(403, "account_suspended", "This account cannot create transactions.")
    if mode == "live" and not merchant.live_enabled:
        raise ApiError(403, "live_not_enabled", "Live mode is not enabled for this account yet.")


def _check_amount(amount: int) -> None:
    if amount < MIN_AMOUNT:
        raise ApiError(422, "amount_too_small", f"The minimum amount is {MIN_AMOUNT} XAF.")


def _normalize(phone: str) -> str:
    try:
        return normalize_phone(phone)
    except InvalidPhoneNumber as exc:
        raise ApiError(422, "invalid_phone", str(exc)) from exc


async def _check_limits(session: AsyncSession, merchant: Merchant, mode: str, type_: str, amount: int) -> None:
    if mode != "live":
        return
    if amount > merchant.per_txn_limit:
        raise ApiError(422, "amount_too_large", f"The per-transaction limit is {merchant.per_txn_limit} XAF.")
    day_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total = (
        await session.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.merchant_id == merchant.id,
                Transaction.mode == "live",
                Transaction.type == type_,
                Transaction.status.in_(("created", "pending", "succeeded")),
                Transaction.created_at >= day_start,
            )
        )
    ).scalar_one()
    if total + amount > merchant.daily_limit:
        raise ApiError(422, "daily_limit_exceeded", f"The daily limit is {merchant.daily_limit} XAF.")


async def _find_idempotent(session: AsyncSession, merchant_id, mode: str, key: str | None) -> Transaction | None:
    if not key:
        return None
    return (
        await session.execute(
            select(Transaction)
            .where(Transaction.merchant_id == merchant_id, Transaction.mode == mode, Transaction.idempotency_key == key)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


def _assert_same_request(existing: Transaction, type_: str, amount: int, phone: str) -> None:
    if existing.type != type_ or existing.amount != amount or existing.phone_number != phone:
        raise ApiError(409, "idempotency_conflict", "This Idempotency-Key was already used with different parameters.")


def _registry_provider(registry: ProviderRegistry, mode: str):
    try:
        return registry.for_mode(mode)
    except ProviderNotConfigured as exc:
        raise ApiError(503, "provider_unavailable", GENERIC_UNAVAILABLE) from exc


def _new_tx(merchant: Merchant, mode: str, type_: str, prefix: str, **fields) -> Transaction:
    return Transaction(id=uuid.uuid4(), public_id=new_public_id(prefix), merchant_id=merchant.id, mode=mode, type=type_, status="created", **fields)


# ------------------------------------------------------------------ collections
async def create_collection(
    session: AsyncSession,
    registry: ProviderRegistry,
    *,
    merchant: Merchant,
    mode: str,
    amount: int,
    phone: str,
    description: str | None,
    merchant_reference: str | None,
    idempotency_key: str | None,
    user_metadata: dict | None = None,
    internal: dict | None = None,
) -> tuple[Transaction, bool]:
    """Returns (transaction, created_now). created_now=False means an idempotent replay."""
    _check_can_transact(merchant, mode)
    merchant_id = merchant.id  # plain value: ORM objects are expired by any later rollback
    _check_amount(amount)
    phone = _normalize(phone)
    existing = await _find_idempotent(session, merchant_id, mode, idempotency_key)
    if existing:
        _assert_same_request(existing, "collection", amount, phone)
        return existing, False
    _registry_provider(registry, mode)  # fail fast if the provider is not configured
    await _check_limits(session, merchant, mode, "collection", amount)

    tx = _new_tx(
        merchant, mode, "collection", "col",
        amount=amount,
        fee=compute_fee(amount, merchant.collection_fee_bps),
        phone_number=phone,
        description=description,
        merchant_reference=merchant_reference,
        idempotency_key=idempotency_key,
        provider=registry.provider_name(mode),
        meta={"user": user_metadata or {}, **(internal or {})},
    )
    session.add(tx)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await _find_idempotent(session, merchant_id, mode, idempotency_key)
        if existing:
            return existing, False
        raise
    await session.commit()

    provider = _registry_provider(registry, mode)
    request = CollectRequest(amount=tx.amount, phone=tx.phone_number, description=tx.description or "Payment", external_reference=str(tx.id))
    try:
        result = await provider.collect(request)
    except ProviderRejected as exc:
        logger.warning("collect rejected tx=%s: %s", tx.public_id, exc)
        await _fail(session, tx.id, "provider_rejected", GENERIC_REJECTED, str(exc))
        return tx, True
    except ProviderAuthError as exc:
        logger.error("provider auth problem on collect tx=%s: %s", tx.public_id, exc)
        await _fail(session, tx.id, "provider_unavailable", GENERIC_UNAVAILABLE, str(exc))
        return tx, True
    except ProviderUnavailable as exc:
        logger.error("collect outcome unknown tx=%s: %s", tx.public_id, exc)
        return tx, True  # stays 'created'; a Campay webhook (external_reference) or expiry resolves it

    tx.provider_reference = result.reference
    tx.operator = result.operator
    tx.provider_status = result.status.value.upper()
    tx.status = "pending"
    await session.commit()
    if provider.settles_immediately:
        await sync_with_provider(session, registry, tx.id)
    return tx, True


# ------------------------------------------------------------------ payouts
async def create_payout(
    session: AsyncSession,
    registry: ProviderRegistry,
    *,
    merchant: Merchant,
    mode: str,
    amount: int,
    phone: str,
    description: str | None,
    merchant_reference: str | None,
    idempotency_key: str | None,
    user_metadata: dict | None = None,
    internal: dict | None = None,
) -> tuple[Transaction, bool]:
    _check_can_transact(merchant, mode)
    merchant_id = merchant.id  # plain value: ORM objects are expired by any later rollback
    _check_amount(amount)
    phone = _normalize(phone)
    existing = await _find_idempotent(session, merchant_id, mode, idempotency_key)
    if existing:
        _assert_same_request(existing, "payout", amount, phone)
        return existing, False
    _registry_provider(registry, mode)
    await _check_limits(session, merchant, mode, "payout", amount)

    fee = compute_fee(amount, merchant.payout_fee_bps)
    total = amount + fee
    available = await ledger.get_account(session, merchant.id, mode, "merchant_available", lock=True)
    if available.balance < total:
        balance_now = available.balance  # read BEFORE rollback: rollback expires every ORM object in the session
        await session.rollback()
        raise ApiError(402, "insufficient_funds", f"Available balance is {balance_now} XAF, {total} XAF needed (amount + fee).")

    tx = _new_tx(
        merchant, mode, "payout", "pay",
        amount=amount,
        fee=fee,
        phone_number=phone,
        description=description,
        merchant_reference=merchant_reference,
        idempotency_key=idempotency_key,
        provider=registry.provider_name(mode),
        meta={"user": user_metadata or {}, **(internal or {})},
    )
    session.add(tx)
    try:
        await session.flush()
        await ledger.post_payout_hold(session, tx)
    except IntegrityError:
        await session.rollback()
        existing = await _find_idempotent(session, merchant_id, mode, idempotency_key)
        if existing:
            return existing, False
        raise ApiError(402, "insufficient_funds", "Insufficient available balance.")
    await session.commit()

    provider = _registry_provider(registry, mode)
    request = PayoutRequest(amount=tx.amount, phone=tx.phone_number, description=tx.description or "Payout", external_reference=str(tx.id))
    try:
        result = await provider.payout(request)
    except ProviderRejected as exc:
        logger.warning("payout rejected tx=%s: %s", tx.public_id, exc)
        await _fail(session, tx.id, "provider_rejected", GENERIC_REJECTED, str(exc))
        return tx, True
    except ProviderAuthError as exc:
        logger.error("provider auth problem on payout tx=%s: %s", tx.public_id, exc)
        await _fail(session, tx.id, "provider_unavailable", GENERIC_UNAVAILABLE, str(exc))
        return tx, True
    except ProviderUnavailable as exc:
        # Money may or may not have left. NEVER release the hold automatically.
        logger.error("PAYOUT OUTCOME UNKNOWN tx=%s: %s", tx.public_id, exc)
        tx.status = "pending"
        tx.provider_status = "UNKNOWN"
        await session.commit()
        return tx, True

    tx.provider_reference = result.reference
    tx.operator = result.operator
    tx.provider_status = result.status.value.upper()
    tx.status = "pending"
    await session.commit()
    if result.status is not ProviderStatus.PENDING:
        await apply_provider_status(session, tx.id, result.status, operator=result.operator)
        await session.commit()
    elif provider.settles_immediately:
        await sync_with_provider(session, registry, tx.id)
    return tx, True


# ------------------------------------------------------------------ settlement
async def _fail(session: AsyncSession, tx_id, code: str, message: str, provider_message: str | None = None) -> None:
    await apply_provider_status(
        session, tx_id, ProviderStatus.FAILED, failure_code=code, failure_message=message, provider_message=provider_message
    )
    await session.commit()


async def apply_provider_status(
    session: AsyncSession,
    tx_id,
    status: ProviderStatus,
    *,
    failure_code: str | None = None,
    failure_message: str | None = None,
    provider_message: str | None = None,
    operator: str | None = None,
    provider_reference: str | None = None,
    provider_status: str | None = None,
) -> tuple[Transaction, bool]:
    """Idempotent state transition under a row lock. Caller commits. Returns (tx, changed)."""
    await ledger.set_lock_timeout(session)
    tx = (
        await session.execute(
            select(Transaction).where(Transaction.id == tx_id).with_for_update().execution_options(populate_existing=True)
        )
    ).scalar_one()
    if tx.status in TERMINAL:
        return tx, False
    if provider_reference and not tx.provider_reference:
        tx.provider_reference = provider_reference
    if operator:
        tx.operator = operator
    if provider_status:
        tx.provider_status = provider_status
    if status is ProviderStatus.PENDING:
        if tx.status == "created":
            tx.status = "pending"
        await session.flush()
        return tx, False

    succeeded = status is ProviderStatus.SUCCEEDED
    if tx.type == "collection":
        if succeeded:
            await ledger.post_collection_settled(session, tx)
    elif succeeded:
        await ledger.post_payout_settled(session, tx)
    else:
        await ledger.post_payout_released(session, tx)

    tx.status = "succeeded" if succeeded else "failed"
    tx.completed_at = utcnow()
    if not succeeded:
        tx.failure_code = failure_code or "provider_failed"
        tx.failure_message = failure_message or "The transaction was not completed."
    if provider_message:
        tx.meta = {**(tx.meta or {}), "provider_message": provider_message}

    session_id = (tx.meta or {}).get("checkout_session")
    if succeeded and tx.type == "collection" and session_id:
        await session.execute(
            update(CheckoutSession)
            .where(CheckoutSession.public_id == session_id, CheckoutSession.status == "open")
            .values(status="paid", paid_at=utcnow(), transaction_id=tx.id)
        )
    await enqueue_event(session, tx, f"{tx.type}.{'succeeded' if succeeded else 'failed'}")
    await session.flush()
    return tx, True


async def sync_with_provider(session: AsyncSession, registry: ProviderRegistry, tx_id) -> bool:
    """Fetch the provider's view of a transaction and apply it. Never raises provider errors."""
    tx = await session.get(Transaction, tx_id)
    if tx is None or tx.status in TERMINAL or not tx.provider_reference:
        return False
    try:
        info = await registry.for_mode(tx.mode).get_transaction(tx.provider_reference)
    except (ProviderError, ProviderNotConfigured) as exc:
        logger.warning("sync failed tx=%s: %s", tx.public_id, exc)
        return False
    _, changed = await apply_provider_status(
        session,
        tx.id,
        info.status,
        failure_message=GENERIC_REJECTED if info.status is ProviderStatus.FAILED else None,
        failure_code="provider_failed",
        provider_message=info.failure_reason,
        operator=info.operator,
        provider_status=str(info.raw.get("status") or "") or None,
    )
    await session.commit()
    return changed


# ------------------------------------------------------------------ on-demand refresh
_last_check: dict = {}
_MIN_RECHECK_SECONDS = 3.0


async def refresh_if_pending(session: AsyncSession, registry: ProviderRegistry, tx: Transaction) -> Transaction:
    """If a transaction is still pending, ask the provider for its latest status (at most every few seconds per
    transaction). This is what makes live payments settle without a public webhook URL."""
    if tx.status not in ("created", "pending") or not tx.provider_reference or tx.provider == "simulated":
        return tx
    now = time.monotonic()
    if now - _last_check.get(tx.id, 0.0) < _MIN_RECHECK_SECONDS:
        return tx
    if len(_last_check) > 5000:
        _last_check.clear()
    _last_check[tx.id] = now
    await sync_with_provider(session, registry, tx.id)
    return tx


async def refresh_many(session: AsyncSession, registry: ProviderRegistry, txs: list[Transaction], limit: int = 5) -> None:
    for tx in [t for t in txs if t.status in ("created", "pending")][:limit]:
        await refresh_if_pending(session, registry, tx)


# ------------------------------------------------------------------ background reconciliation
async def reconcile_pending(session: AsyncSession, registry: ProviderRegistry, limit: int = 20) -> dict:
    cutoff = utcnow() - timedelta(seconds=30)  # give inbound webhooks a head start
    rows = (
        await session.execute(
            select(Transaction.id)
            .where(Transaction.status == "pending", Transaction.provider_reference.is_not(None), Transaction.updated_at < cutoff)
            .order_by(Transaction.updated_at)
            .limit(limit)
        )
    ).scalars().all()
    changed = 0
    for tx_id in rows:
        if await sync_with_provider(session, registry, tx_id):
            changed += 1
        else:  # rotate: an UPDATE fires the updated_at trigger so other rows get their turn
            await session.execute(
                update(Transaction).where(Transaction.id == tx_id, Transaction.status == "pending")
                .values(provider_status=func.coalesce(Transaction.provider_status, "PENDING"))
            )
            await session.commit()
    return {"checked": len(rows), "settled": changed}


async def expire_stale(session: AsyncSession) -> dict:
    now = utcnow()
    ids = (
        await session.execute(
            select(Transaction.id)
            .where(
                Transaction.type == "collection",
                Transaction.status == "created",
                Transaction.provider_reference.is_(None),
                Transaction.created_at < now - timedelta(minutes=15),
            )
            .limit(50)
        )
    ).scalars().all()
    expired = 0
    for tx_id in ids:
        await ledger.set_lock_timeout(session)
        tx = (
            await session.execute(
                select(Transaction).where(Transaction.id == tx_id).with_for_update().execution_options(populate_existing=True)
            )
        ).scalar_one()
        if tx.status != "created":
            await session.rollback()
            continue
        tx.status = "expired"
        tx.completed_at = now
        tx.failure_code = "expired"
        tx.failure_message = "The payment was not started in time."
        await enqueue_event(session, tx, "collection.expired")
        await session.commit()
        expired += 1
    sessions = await session.execute(
        update(CheckoutSession).where(CheckoutSession.status == "open", CheckoutSession.expires_at < now).values(status="expired")
    )
    await session.commit()
    # payouts whose outcome we could not determine: surfaced, never auto-resolved
    needs_review = (
        await session.execute(
            select(func.count()).select_from(Transaction).where(
                Transaction.type == "payout",
                Transaction.status == "pending",
                Transaction.provider_reference.is_(None),
                Transaction.updated_at < now - timedelta(minutes=2),
            )
        )
    ).scalar_one()
    return {"collections_expired": expired, "sessions_expired": sessions.rowcount, "payouts_needing_review": needs_review}


# ------------------------------------------------------------------ queries
async def get_by_public_id(session: AsyncSession, merchant_id, mode: str, public_id: str, type_: str | None = None) -> Transaction:
    stmt = select(Transaction).where(
        Transaction.public_id == public_id, Transaction.merchant_id == merchant_id, Transaction.mode == mode
    )
    if type_:
        stmt = stmt.where(Transaction.type == type_)
    tx = (await session.execute(stmt.execution_options(populate_existing=True))).scalar_one_or_none()
    if tx is None:
        raise ApiError(404, "not_found", "Transaction not found.")
    return tx


async def list_transactions(
    session: AsyncSession, merchant_id, mode: str, *, type_: str | None, status: str | None, limit: int, offset: int
) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.merchant_id == merchant_id, Transaction.mode == mode)
    if type_:
        stmt = stmt.where(Transaction.type == type_)
    if status == "pending":
        stmt = stmt.where(Transaction.status.in_(("created", "pending")))
    elif status:
        stmt = stmt.where(Transaction.status == status)
    stmt = stmt.order_by(Transaction.created_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())
