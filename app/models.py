"""ORM mapping of schema.sql.

schema.sql is the source of truth (constraints, triggers, indexes live there).
Never call Base.metadata.create_all(); these classes only map existing tables.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Computed, DateTime, ForeignKey, Integer, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_NOW = text("now()")


class Base(DeclarativeBase):
    # fetch server-side defaults (ids, timestamps) via RETURNING on INSERT; async code can't lazy-load them
    __mapper_args__ = {"eager_defaults": True}


def _uuid_pk():
    return mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _uuid_fk(table: str, *, nullable: bool = False, ondelete: str | None = None):
    return mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{table}.id", ondelete=ondelete), nullable=nullable)


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    live_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    kyc_level: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    per_txn_limit: Mapped[int] = mapped_column(BigInteger, server_default=text("50000"))
    daily_limit: Mapped[int] = mapped_column(BigInteger, server_default=text("200000"))
    collection_fee_bps: Mapped[int] = mapped_column(Integer, server_default=text("250"))
    payout_fee_bps: Mapped[int] = mapped_column(Integer, server_default=text("250"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[uuid.UUID] = _uuid_pk()
    merchant_id: Mapped[uuid.UUID] = _uuid_fk("merchants", ondelete="CASCADE")
    mode: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text)
    prefix: Mapped[str] = mapped_column(Text, unique=True)
    key_hash: Mapped[str] = mapped_column(Text)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"
    id: Mapped[uuid.UUID] = _uuid_pk()
    merchant_id: Mapped[uuid.UUID] = _uuid_fk("merchants", ondelete="CASCADE")
    mode: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    signing_secret: Mapped[str] = mapped_column(Text)
    events: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[uuid.UUID] = _uuid_pk()
    merchant_id: Mapped[uuid.UUID | None] = _uuid_fk("merchants", nullable=True)
    mode: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'XAF'"))
    balance: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))  # trigger-maintained
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    public_id: Mapped[str] = mapped_column(Text, unique=True)
    merchant_id: Mapped[uuid.UUID] = _uuid_fk("merchants")
    mode: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'created'"))
    amount: Mapped[int] = mapped_column(BigInteger)
    fee: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    currency: Mapped[str] = mapped_column(Text, server_default=text("'XAF'"))
    phone_number: Mapped[str] = mapped_column(Text)
    operator: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    merchant_reference: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text, server_default=text("'campay'"))
    provider_reference: Mapped[str | None] = mapped_column(Text)
    provider_status: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text)
    failure_message: Mapped[str | None] = mapped_column(Text)
    # "metadata" is reserved by SQLAlchemy's declarative base, so the attribute is `meta`
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)  # set in app code
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LedgerJournal(Base):
    __tablename__ = "ledger_journals"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaction_id: Mapped[uuid.UUID] = _uuid_fk("transactions")
    kind: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    journal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ledger_journals.id"))
    account_id: Mapped[uuid.UUID] = _uuid_fk("accounts")
    direction: Mapped[str] = mapped_column(Text)  # 'debit' | 'credit'
    amount: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class ProviderEvent(Base):
    __tablename__ = "provider_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, server_default=text("'campay'"))
    dedupe_key: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    signature_valid: Mapped[bool] = mapped_column(Boolean)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    endpoint_id: Mapped[uuid.UUID] = _uuid_fk("webhook_endpoints", ondelete="CASCADE")
    transaction_id: Mapped[uuid.UUID | None] = _uuid_fk("transactions", nullable=True)
    event_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    ledger_total: Mapped[int] = mapped_column(BigInteger)
    provider_balance: Mapped[int] = mapped_column(BigInteger)
    diff: Mapped[int] = mapped_column(BigInteger, Computed("provider_balance - ledger_total", persisted=True))
    note: Mapped[str | None] = mapped_column(Text)


class ApiRequestLog(Base):
    __tablename__ = "api_request_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    merchant_id: Mapped[uuid.UUID | None] = _uuid_fk("merchants", nullable=True, ondelete="SET NULL")
    api_key_id: Mapped[uuid.UUID | None] = _uuid_fk("api_keys", nullable=True, ondelete="SET NULL")
    method: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(INET)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    public_id: Mapped[str] = mapped_column(Text, unique=True)
    merchant_id: Mapped[uuid.UUID] = _uuid_fk("merchants")
    mode: Mapped[str] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'XAF'"))
    description: Mapped[str | None] = mapped_column(Text)
    merchant_reference: Mapped[str | None] = mapped_column(Text)
    redirect_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    transaction_id: Mapped[uuid.UUID | None] = _uuid_fk("transactions", nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
