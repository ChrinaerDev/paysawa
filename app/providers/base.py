"""Provider abstraction. Nothing outside app/providers/ may know about Campay."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# ------------------------------------------------------------------ errors
class ProviderError(Exception):
    """Base class for provider failures."""


class ProviderRejected(ProviderError):
    """The provider answered with a definite refusal (4xx). No money moved:
    the transaction can safely be marked failed."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ProviderUnavailable(ProviderError):
    """Timeout, network error, 429 or 5xx. The OUTCOME IS UNKNOWN: the provider may
    have executed the request. Never mark the transaction failed on this; leave it
    pending and let /internal/tick reconcile it by external_reference."""


class ProviderAuthError(ProviderError):
    """Our credentials were refused. Operational alert, not a merchant error."""


class InvalidPhoneNumber(ValueError):
    """Phone number cannot be normalized to the provider's format."""


# --------------------------------------------------------------- dataclasses
@dataclass(frozen=True)
class CollectRequest:
    amount: int                 # XAF, integer
    phone: str
    description: str
    external_reference: str     # our transactions.id
    currency: str = "XAF"


@dataclass(frozen=True)
class PayoutRequest:
    amount: int
    phone: str
    description: str
    external_reference: str
    currency: str = "XAF"


@dataclass(frozen=True)
class ProviderResult:
    reference: str
    status: ProviderStatus
    operator: str | None = None
    ussd_code: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderTransaction:
    reference: str
    status: ProviderStatus
    external_reference: str | None = None
    amount: int | None = None
    operator: str | None = None
    failure_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderBalance:
    total: int
    mtn: int
    orange: int
    currency: str = "XAF"


@dataclass(frozen=True)
class WebhookEvent:
    """Untrusted hint that something changed. ALWAYS re-fetch with get_transaction()
    before crediting anyone."""
    reference: str
    external_reference: str | None
    status: ProviderStatus
    raw: dict[str, Any] = field(default_factory=dict)


class Provider(ABC):
    name: str
    settles_immediately: bool = False  # True only for the simulated sandbox provider

    @abstractmethod
    async def collect(self, req: CollectRequest) -> ProviderResult: ...

    @abstractmethod
    async def payout(self, req: PayoutRequest) -> ProviderResult: ...

    @abstractmethod
    async def get_transaction(self, reference: str) -> ProviderTransaction: ...

    @abstractmethod
    async def get_balance(self) -> ProviderBalance: ...

    @abstractmethod
    def verify_webhook(self, params: Mapping[str, str]) -> WebhookEvent: ...

    async def aclose(self) -> None:  # optional
        return None
