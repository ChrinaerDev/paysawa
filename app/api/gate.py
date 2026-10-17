"""Public pay-gate API (no auth): the hosted payment page talks to these endpoints.
The session id is the capability. Abuse is limited by per-IP rate limits and a 3-attempt cap."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_registry
from app.db import get_session
from app.models import Merchant, Transaction
from app.providers.registry import ProviderRegistry
from app.ratelimit import RateLimiter, client_ip
from app.services import checkout as checkout_service
from app.services.checkout import MAX_ATTEMPTS
from app.services.jobs import run_deliveries
from app.services.serializers import iso, public_status

router = APIRouter(prefix="/gate", tags=["pay gate (public)"])
_pay_limiter = RateLimiter(8, 60)
_read_limiter = RateLimiter(120, 60)


class PayIn(BaseModel):
    phone: str = Field(min_length=9, max_length=20)


async def _view(session: AsyncSession, cs) -> dict:
    merchant = await session.get(Merchant, cs.merchant_id)
    tx = await session.get(Transaction, cs.transaction_id, populate_existing=True) if cs.transaction_id else None
    state = checkout_service.effective_status(cs)
    return {
        "id": cs.public_id,
        "mode": cs.mode,
        "status": state,  # open | paid | expired
        "merchant_name": merchant.name if merchant else None,
        "amount": cs.amount,
        "currency": cs.currency,
        "description": cs.description,
        "merchant_reference": cs.merchant_reference,
        "expires_at": iso(cs.expires_at),
        "attempts_left": max(0, MAX_ATTEMPTS - cs.attempts),
        "payment": None if tx is None else {
            "status": public_status(tx),  # pending | succeeded | failed | expired
            "failure_message": tx.failure_message,
            "operator": tx.operator,
        },
        # only exposed once paid: the page sends the customer back to the merchant
        "redirect_url": cs.redirect_url if state == "paid" else None,
    }


@router.get("/sessions/{public_id}")
async def get_session_info(public_id: str, request: Request, session: AsyncSession = Depends(get_session)):
    _read_limiter.check(client_ip(request))
    cs = await checkout_service.get_public(session, public_id)
    return await _view(session, cs)


@router.get("/sessions/{public_id}/status")
async def get_session_status(public_id: str, request: Request, session: AsyncSession = Depends(get_session)):
    """Cheap endpoint for the page to poll every 2-3 seconds while the customer approves on their phone."""
    _read_limiter.check(client_ip(request))
    cs = await checkout_service.get_public(session, public_id)
    return await _view(session, cs)


@router.post("/sessions/{public_id}/pay")
async def pay(
    public_id: str,
    body: PayIn,
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    registry: ProviderRegistry = Depends(get_registry),
):
    _pay_limiter.check(client_ip(request))
    cs, _tx = await checkout_service.pay(session, registry, public_id, body.phone)
    background.add_task(run_deliveries, request.app.state)
    return await _view(session, cs)
