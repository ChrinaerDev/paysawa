"""Double-entry postings. Convention: balance = credits - debits (see backend.md).
DB triggers enforce balanced journals, append-only entries and merchant_no_overdraft."""
from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Account, LedgerEntry, LedgerJournal, Transaction


async def set_lock_timeout(session: AsyncSession, seconds: int = 10) -> None:
    """Fail fast instead of hanging if another transaction holds the row (applies to this transaction only)."""
    await session.execute(text(f"SET LOCAL lock_timeout = '{int(seconds)}s'"))


async def get_account(
    session: AsyncSession, merchant_id: uuid.UUID | None, mode: str, type_: str, *, lock: bool = False
) -> Account:
    stmt = select(Account).where(Account.mode == mode, Account.type == type_)
    stmt = stmt.where(Account.merchant_id.is_(None) if merchant_id is None else Account.merchant_id == merchant_id)
    stmt = stmt.execution_options(populate_existing=True)
    if lock:
        await set_lock_timeout(session)
        stmt = stmt.with_for_update()
    account = (await session.execute(stmt)).scalar_one_or_none()
    if account is None:
        raise ApiError(
            500,
            "ledger_not_initialized",
            f"Ledger account {type_}/{mode} is missing. Run: python -m scripts.bootstrap",
        )
    return account


async def post_journal(
    session: AsyncSession, transaction_id: uuid.UUID, kind: str, lines: list[tuple[uuid.UUID, str, int]]
) -> bool:
    """Posts one balanced journal. Idempotent: returns False if (transaction, kind) was already posted."""
    stmt = (
        pg_insert(LedgerJournal)
        .values(transaction_id=transaction_id, kind=kind)
        .on_conflict_do_nothing(index_elements=["transaction_id", "kind"])
        .returning(LedgerJournal.id)
    )
    journal_id = (await session.execute(stmt)).scalar_one_or_none()
    if journal_id is None:
        return False
    for account_id, direction, amount in lines:
        session.add(LedgerEntry(journal_id=journal_id, account_id=account_id, direction=direction, amount=amount))
    await session.flush()
    return True


async def post_collection_settled(session: AsyncSession, tx: Transaction) -> bool:
    float_acct = await get_account(session, None, tx.mode, "provider_float")
    available = await get_account(session, tx.merchant_id, tx.mode, "merchant_available")
    lines = [(float_acct.id, "debit", tx.amount), (available.id, "credit", tx.amount - tx.fee)]
    if tx.fee > 0:
        fees = await get_account(session, None, tx.mode, "platform_fees")
        lines.append((fees.id, "credit", tx.fee))
    return await post_journal(session, tx.id, "collection_settled", lines)


async def post_payout_hold(session: AsyncSession, tx: Transaction) -> bool:
    available = await get_account(session, tx.merchant_id, tx.mode, "merchant_available")
    held = await get_account(session, tx.merchant_id, tx.mode, "merchant_held")
    total = tx.amount + tx.fee
    return await post_journal(session, tx.id, "payout_hold", [(available.id, "debit", total), (held.id, "credit", total)])


async def post_payout_settled(session: AsyncSession, tx: Transaction) -> bool:
    held = await get_account(session, tx.merchant_id, tx.mode, "merchant_held")
    float_acct = await get_account(session, None, tx.mode, "provider_float")
    lines = [(held.id, "debit", tx.amount + tx.fee), (float_acct.id, "credit", tx.amount)]
    if tx.fee > 0:
        fees = await get_account(session, None, tx.mode, "platform_fees")
        lines.append((fees.id, "credit", tx.fee))
    return await post_journal(session, tx.id, "payout_settled", lines)


async def post_payout_released(session: AsyncSession, tx: Transaction) -> bool:
    held = await get_account(session, tx.merchant_id, tx.mode, "merchant_held")
    available = await get_account(session, tx.merchant_id, tx.mode, "merchant_available")
    total = tx.amount + tx.fee
    return await post_journal(
        session, tx.id, "payout_released", [(held.id, "debit", total), (available.id, "credit", total)]
    )
