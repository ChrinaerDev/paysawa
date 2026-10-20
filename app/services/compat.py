"""Campay-shaped representations. Pure functions: no database, no framework."""
from decimal import Decimal, InvalidOperation

_STATUS = {"created": "PENDING", "pending": "PENDING", "succeeded": "SUCCESSFUL", "failed": "FAILED", "expired": "FAILED"}


def campay_status(status: str) -> str:
    return _STATUS.get(status, "PENDING")


def ussd_for(operator: str | None) -> str:
    return "*126#" if (operator or "").upper().startswith("MTN") else "#150*50#"


def parse_amount(value) -> int:
    """Campay clients send amounts as strings or numbers. XAF has no decimals."""
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError("amount must be a number") from None
    if d <= 0 or d != d.to_integral_value():
        raise ValueError("amount must be a whole positive number of XAF")
    return int(d)


def campay_params(tx) -> dict:
    """Query parameters of a Campay-style webhook (without `signature`)."""
    return {
        "status": campay_status(tx.status),
        "reference": tx.public_id,
        "amount": str(tx.amount),
        "currency": tx.currency,
        "operator": tx.operator or "",
        "code": "",
        "operator_reference": tx.provider_reference or "",
        "external_reference": tx.merchant_reference or "",
    }


def campay_transaction(tx) -> dict:
    """Body of GET /api/transaction/{reference}/."""
    data = {
        "reference": tx.public_id,
        "status": campay_status(tx.status),
        "amount": tx.amount,
        "currency": tx.currency,
        "operator": tx.operator or "",
        "code": "",
        "operator_reference": tx.provider_reference or "",
        "description": tx.description or "",
        "external_reference": tx.merchant_reference or "",
        "external_user": None,
    }
    if tx.failure_message:
        data["reason"] = tx.failure_message
    return data
