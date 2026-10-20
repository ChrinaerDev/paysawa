from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Account, ApiKey, Merchant
from app.security import hash_password, make_api_key


async def create_merchant(session: AsyncSession, *, name: str, email: str, password: str, live_enabled: bool = False) -> Merchant:
    email = email.strip().lower()
    if len(password) < 8:
        raise ApiError(422, "weak_password", "Password must be at least 8 characters.")
    taken = (await session.execute(select(Merchant.id).where(Merchant.email == email))).first()
    if taken:
        raise ApiError(409, "email_taken", "An account with this email already exists.")
    merchant = Merchant(
        id=uuid.uuid4(),
        name=name.strip(),
        email=email,
        password_hash=await asyncio.to_thread(hash_password, password),
        live_enabled=live_enabled,
    )
    session.add(merchant)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "email_taken", "An account with this email already exists.") from exc
    for mode in ("test", "live"):
        for type_ in ("merchant_available", "merchant_held"):
            session.add(Account(id=uuid.uuid4(), merchant_id=merchant.id, mode=mode, type=type_, currency="XAF"))
    await session.commit()
    return merchant


async def issue_api_key(session: AsyncSession, merchant: Merchant, mode: str, label: str | None, secret: str) -> tuple[ApiKey, str]:
    if not secret:
        raise ApiError(500, "not_configured", "Set API_KEY_SECRET (or JWT_SECRET) in .env before creating API keys.")
    key_id = uuid.uuid4()
    full, prefix, key_hash = make_api_key(mode, key_id, secret)
    key = ApiKey(id=key_id, merchant_id=merchant.id, mode=mode, label=label, prefix=prefix, key_hash=key_hash)
    session.add(key)
    await session.commit()
    return key, full


async def get_by_email(session: AsyncSession, email: str) -> Merchant | None:
    return (await session.execute(select(Merchant).where(Merchant.email == email.strip().lower()))).scalar_one_or_none()
