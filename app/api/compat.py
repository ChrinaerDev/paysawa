"""Campay-compatible API: what Campay exposes to Paysawa, Paysawa exposes to its merchants.

    POST /api/token/                  {username, password}            -> {token, expires_in}
    POST /api/collect/                {amount, currency, from, description, external_reference} -> {reference, ussd_code, operator}
    POST /api/withdraw/               {amount, currency, to, description, external_reference}   -> {reference, status, ...}
    GET  /api/transaction/{reference}/                               -> {reference, status, amount, ...}
    GET  /api/balance/                                               -> {total_balance, ...}
    POST /api/get_payment_link/       {amount, currency, description, external_reference, redirect_url} -> {link}

Auth header: `Authorization: Token <token>`. Errors are flat: {"message", "code"}.
"""
from __future__ import annotations

import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AppCaller, app_caller, get_registry
from app.config import Settings, get_settings
from app.db import get_session
from app.errors import ApiError
from app.models import Account, App, CheckoutSession, Transaction
from app.providers.registry import ProviderRegistry
from app.ratelimit import RateLimiter, client_ip
from app.security import create_app_token, hash_api_key
from app.services import checkout as checkout_service
from app.services import transactions as tx_service
from app.services.compat import campay_status, campay_transaction, parse_amount, ussd_for
from app.services.jobs import run_deliveries, start_watch
from app.services.serializers import session_to_dict

TOKEN_TTL = 3600
_token_limiter = RateLimiter(20, 300)


class CompatRoute(APIRoute):
    """Renders ApiError the way Campay-style clients expect: {"message": ..., "code": ...}."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original(request)
            except ApiError as exc:
                return JSONResponse(status_code=exc.status_code, content={"message": exc.message, "code": exc.code})
            except RequestValidationError as exc:  # missing/invalid fields: same flat shape as every other error here
                first = exc.errors()[0] if exc.errors() else {}
                where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
                return JSONResponse(status_code=422, content={"message": f"{where}: {first.get('msg', 'invalid value')}".strip(": "), "code": "invalid_request"})

        return handler


router = APIRouter(prefix="/api", tags=["Apps API"], route_class=CompatRoute)


class _Body(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class TokenIn(_Body):
    username: str
    password: str


class CollectIn(_Body):
    amount: str | int | float
    currency: str = "XAF"
    from_: str = Field(alias="from")
    description: str = ""
    external_reference: str | None = None


class WithdrawIn(_Body):
    amount: str | int | float
    currency: str = "XAF"
    to: str
    description: str = ""
    external_reference: str | None = None


class LinkIn(_Body):
    amount: str | int | float
    currency: str = "XAF"
    from_: str | None = Field(default=None, alias="from")
    description: str = ""
    external_reference: str | None = None
    redirect_url: str | None = None
    failure_redirect_url: str | None = None  # accepted for compatibility, not used yet


def _amount(value) -> int:
    try:
        return parse_amount(value)
    except ValueError as exc:
        raise ApiError(400, "invalid_amount", str(exc)) from exc


def _currency(value: str) -> None:
    if value.upper() != "XAF":
        raise ApiError(400, "invalid_currency", "Only XAF is supported.")


@router.post("/token/")
async def token(body: TokenIn, request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    _token_limiter.check(f"{client_ip(request)}:{body.username}")
    app = (await session.execute(select(App).where(App.username == body.username, App.revoked_at.is_(None)))).scalar_one_or_none()
    if app is None or not hmac.compare_digest(app.password_hash, hash_api_key(body.password)):
        raise ApiError(401, "invalid_credentials", "Invalid app username or password.")
    return {"token": create_app_token(app.id, settings.jwt_secret, TOKEN_TTL), "expires_in": TOKEN_TTL}


@router.post("/collect/")
async def collect(
    body: CollectIn, request: Request, background: BackgroundTasks,
    caller: AppCaller = Depends(app_caller), session: AsyncSession = Depends(get_session), registry: ProviderRegistry = Depends(get_registry),
):
    _currency(body.currency)
    tx, _ = await tx_service.create_collection(
        session, registry, merchant=caller.merchant, mode=caller.mode, amount=_amount(body.amount), phone=body.from_,
        description=body.description or None, merchant_reference=body.external_reference, idempotency_key=None,
        internal={"app_id": str(caller.app.id)},
    )
    if tx.status in ("created", "pending"):
        start_watch(request.app.state, tx)
    background.add_task(run_deliveries, request.app.state)
    return {"reference": tx.public_id, "ussd_code": ussd_for(tx.operator), "operator": tx.operator or "", "status": campay_status(tx.status)}


@router.post("/withdraw/")
async def withdraw(
    body: WithdrawIn, request: Request, background: BackgroundTasks,
    caller: AppCaller = Depends(app_caller), session: AsyncSession = Depends(get_session), registry: ProviderRegistry = Depends(get_registry),
):
    _currency(body.currency)
    tx, _ = await tx_service.create_payout(
        session, registry, merchant=caller.merchant, mode=caller.mode, amount=_amount(body.amount), phone=body.to,
        description=body.description or None, merchant_reference=body.external_reference, idempotency_key=None,
        internal={"app_id": str(caller.app.id)},
    )
    if tx.status in ("created", "pending"):
        start_watch(request.app.state, tx)
    background.add_task(run_deliveries, request.app.state)
    return {"reference": tx.public_id, "status": campay_status(tx.status), "amount": tx.amount, "currency": tx.currency, "operator": tx.operator or ""}


@router.get("/transaction/{reference}/")
async def transaction(
    reference: str,
    caller: AppCaller = Depends(app_caller), session: AsyncSession = Depends(get_session), registry: ProviderRegistry = Depends(get_registry),
):
    if reference.startswith("cs_"):  # a payment link created with /get_payment_link/
        cs = (
            await session.execute(
                select(CheckoutSession).where(
                    CheckoutSession.public_id == reference, CheckoutSession.merchant_id == caller.merchant.id, CheckoutSession.mode == caller.mode
                ).execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if cs is None:
            raise ApiError(404, "not_found", "Transaction not found.")
        tx = await session.get(Transaction, cs.transaction_id, populate_existing=True) if cs.transaction_id else None
        if tx is not None and tx.status in ("created", "pending"):
            await tx_service.refresh_if_pending(session, registry, tx)
            await session.refresh(cs)
        state = checkout_service.effective_status(cs)
        return {
            "reference": cs.public_id, "status": {"paid": "SUCCESSFUL", "open": "PENDING", "expired": "FAILED"}[state],
            "amount": cs.amount, "currency": cs.currency, "operator": (tx.operator if tx else "") or "", "code": "",
            "operator_reference": tx.public_id if tx else "", "description": cs.description or "",
            "external_reference": cs.merchant_reference or "", "payment_reference": tx.public_id if tx else None,
        }
    tx = await tx_service.get_by_public_id(session, caller.merchant.id, caller.mode, reference)
    return campay_transaction(await tx_service.refresh_if_pending(session, registry, tx))


@router.get("/balance/")
async def balance(caller: AppCaller = Depends(app_caller), session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(Account).where(Account.merchant_id == caller.merchant.id, Account.mode == caller.mode).execution_options(populate_existing=True)
        )
    ).scalars().all()
    available = held = 0
    for acct in rows:
        if acct.type == "merchant_available":
            available = acct.balance
        else:
            held = acct.balance
    # Paysawa keeps ONE balance per merchant: the per-operator fields exist for compatibility and are null.
    return {"total_balance": available, "mtn_balance": None, "orange_balance": None, "held_balance": held, "currency": "XAF"}


@router.post("/get_payment_link/")
async def get_payment_link(
    body: LinkIn, caller: AppCaller = Depends(app_caller), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings),
):
    _currency(body.currency)
    cs = await checkout_service.create_session(
        session, merchant=caller.merchant, mode=caller.mode, amount=_amount(body.amount), description=body.description or None,
        merchant_reference=body.external_reference, redirect_url=body.redirect_url, expires_in_minutes=60, user_metadata=None,
        extra_meta={"app_id": str(caller.app.id)},
    )
    return {"link": session_to_dict(cs, settings.gate_url)["url"], "reference": cs.public_id}
