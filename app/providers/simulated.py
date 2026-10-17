"""Built-in sandbox provider for TEST mode. No network, stateless (survives restarts).

The outcome is decided by the last digits of the phone number and encoded in the
reference, so get_transaction() needs no storage:
  ...0000  -> fails          ...9999  -> stays pending forever       anything else -> succeeds
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping

from app.phone import normalize_phone
from app.providers.base import (
    CollectRequest,
    PayoutRequest,
    Provider,
    ProviderBalance,
    ProviderError,
    ProviderResult,
    ProviderStatus,
    ProviderTransaction,
    WebhookEvent,
)


def _outcome(phone: str) -> str:
    if phone.endswith("0000"):
        return "fail"
    if phone.endswith("9999"):
        return "pend"
    return "ok"


def _operator(phone: str) -> str:
    """Rough prefix heuristic, simulation only."""
    prefix = phone[3:6]  # after 237
    if prefix.startswith(("67", "68")) or prefix in ("650", "651", "652", "653", "654"):
        return "MTN"
    return "ORANGE"


class SimulatedProvider(Provider):
    name = "simulated"
    settles_immediately = True

    def _create(self, kind: str, req: CollectRequest | PayoutRequest) -> ProviderResult:
        phone = normalize_phone(req.phone)
        reference = f"sim_{_outcome(phone)}_{uuid.uuid4().hex}"
        return ProviderResult(
            reference=reference,
            status=ProviderStatus.PENDING,
            operator=_operator(phone),
            raw={"simulated": True, "kind": kind},
        )

    async def collect(self, req: CollectRequest) -> ProviderResult:
        return self._create("collect", req)

    async def payout(self, req: PayoutRequest) -> ProviderResult:
        return self._create("payout", req)

    async def get_transaction(self, reference: str) -> ProviderTransaction:
        parts = reference.split("_")
        outcome = parts[1] if len(parts) > 2 and parts[0] == "sim" else "pend"
        status = {
            "ok": ProviderStatus.SUCCEEDED,
            "fail": ProviderStatus.FAILED,
        }.get(outcome, ProviderStatus.PENDING)
        return ProviderTransaction(
            reference=reference,
            status=status,
            failure_reason="Simulated failure" if status is ProviderStatus.FAILED else None,
            raw={"simulated": True, "status": status.value.upper()},
        )

    async def get_balance(self) -> ProviderBalance:
        return ProviderBalance(total=10**9, mtn=5 * 10**8, orange=5 * 10**8)

    def verify_webhook(self, params: Mapping[str, str]) -> WebhookEvent:
        raise ProviderError("the simulated provider does not send webhooks")
