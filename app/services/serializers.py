from __future__ import annotations

from datetime import datetime, timezone

from app.models import CheckoutSession, Transaction


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def public_status(tx: Transaction) -> str:
    """'created' (we have not reached the provider yet) is shown as 'pending'."""
    return "pending" if tx.status == "created" else tx.status


def tx_to_dict(tx: Transaction) -> dict:
    meta = tx.meta or {}
    return {
        "id": tx.public_id,
        "object": tx.type,  # "collection" | "payout"
        "mode": tx.mode,
        "status": public_status(tx),
        "amount": tx.amount,
        "fee": tx.fee,
        "currency": tx.currency,
        "phone_number": tx.phone_number,
        "operator": tx.operator,
        "description": tx.description,
        "merchant_reference": tx.merchant_reference,
        "failure_code": tx.failure_code,
        "failure_message": tx.failure_message,
        "metadata": meta.get("user", {}),
        "checkout_session": meta.get("checkout_session"),
        "created_at": iso(tx.created_at),
        "completed_at": iso(tx.completed_at),
    }


def session_to_dict(cs: CheckoutSession, pay_gate_url: str) -> dict:
    return {
        "id": cs.public_id,
        "object": "checkout_session",
        "mode": cs.mode,
        "status": cs.status,
        "amount": cs.amount,
        "currency": cs.currency,
        "description": cs.description,
        "merchant_reference": cs.merchant_reference,
        "redirect_url": cs.redirect_url,
        "metadata": (cs.meta or {}).get("user", {}),
        "url": f"{pay_gate_url.rstrip('/')}/{cs.public_id}",
        "expires_at": iso(cs.expires_at),
        "expires_in_seconds": max(0, int((cs.expires_at - datetime.now(timezone.utc)).total_seconds())),
        "created_at": iso(cs.created_at),
        "paid_at": iso(cs.paid_at),
    }
