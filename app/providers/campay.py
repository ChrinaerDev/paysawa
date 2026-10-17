"""Campay implementation of the Provider interface.

Endpoints (from Campay's public SDKs): POST token/, POST collect/, POST withdraw/,
GET transaction/{reference}/, GET balance/. Items marked VERIFY must be confirmed
against Campay's official docs / the demo environment.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any

import httpx
import jwt

from app.phone import normalize_phone
from app.providers.base import (
    CollectRequest,
    PayoutRequest,
    Provider,
    ProviderAuthError,
    ProviderBalance,
    ProviderError,
    ProviderRejected,
    ProviderResult,
    ProviderStatus,
    ProviderTransaction,
    ProviderUnavailable,
    WebhookEvent,
)

_STATUS_MAP = {
    "PENDING": ProviderStatus.PENDING,
    "SUCCESSFUL": ProviderStatus.SUCCEEDED,
    "SUCCESS": ProviderStatus.SUCCEEDED,
    "FAILED": ProviderStatus.FAILED,
}


def map_status(value: Any) -> ProviderStatus:
    """Unknown statuses stay PENDING so reconciliation keeps looking at them."""
    return _STATUS_MAP.get(str(value or "").upper(), ProviderStatus.PENDING)


def _error_message(data: Any) -> str | None:
    if isinstance(data, dict):
        for key in ("message", "detail", "error", "reason"):
            if data.get(key):
                return str(data[key])
    return None


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


class CampayProvider(Provider):
    name = "campay"

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        webhook_key: str = "",
        client: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
    ):
        self._base_url = base_url.rstrip("/") + "/"
        self._username = username
        self._password = password
        self._webhook_key = webhook_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------- auth
    async def _get_token(self, *, force: bool = False) -> str:
        async with self._lock:
            if not force and self._token and time.monotonic() < self._token_expires_at:
                return self._token
            try:
                resp = await self._client.post(
                    self._base_url + "token/",
                    json={"username": self._username, "password": self._password},
                )
            except httpx.HTTPError as exc:
                raise ProviderUnavailable(f"campay token request failed: {type(exc).__name__}") from exc
            if resp.status_code >= 500 or resp.status_code == 429:
                raise ProviderUnavailable(f"campay token endpoint returned {resp.status_code}")
            if resp.status_code >= 400:
                raise ProviderAuthError("campay refused our credentials")
            try:
                data = resp.json()
            except ValueError:
                data = {}
            token = data.get("token") if isinstance(data, dict) else None
            if not token:
                raise ProviderAuthError("campay token response had no token")
            ttl = _to_int(data.get("expires_in")) or 120  # VERIFY real token lifetime
            self._token = token
            self._token_expires_at = time.monotonic() + max(ttl - 20, 10)
            return token

    # ---------------------------------------------------------- transport
    async def _send(self, method: str, path: str, json: dict | None) -> httpx.Response:
        token = await self._get_token()
        try:
            return await self._client.request(
                method,
                self._base_url + path,
                json=json,
                headers={"Authorization": f"Token {token}"},
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"campay request failed: {type(exc).__name__}") from exc

    async def _call(self, method: str, path: str, json: dict | None = None) -> dict[str, Any]:
        resp = await self._send(method, path, json)
        if resp.status_code == 401:  # token expired or revoked: refresh once and retry
            await self._get_token(force=True)
            resp = await self._send(method, path, json)
        try:
            data = resp.json()
        except ValueError:
            data = {}
        code = resp.status_code
        if code >= 500 or code == 429:
            raise ProviderUnavailable(f"campay returned {code}")
        if code in (401, 403):
            raise ProviderAuthError("campay refused our credentials")
        if code >= 400:
            raise ProviderRejected(_error_message(data) or f"campay returned {code}", status_code=code)
        if not isinstance(data, dict):
            raise ProviderUnavailable("campay returned an unexpected response body")
        return data

    # ------------------------------------------------------------ actions
    async def collect(self, req: CollectRequest) -> ProviderResult:
        payload = {
            "amount": str(req.amount),
            "currency": req.currency,
            "from": normalize_phone(req.phone),
            "description": req.description,
            "external_reference": req.external_reference,
        }
        data = await self._call("POST", "collect/", payload)
        reference = data.get("reference")
        if not reference:  # accepted but unidentifiable: outcome unknown
            raise ProviderUnavailable("campay collect response had no reference")
        return ProviderResult(
            reference=str(reference),
            status=ProviderStatus.PENDING,  # the customer still has to approve on their phone
            operator=data.get("operator"),
            ussd_code=data.get("ussd_code"),
            raw=data,
        )

    async def payout(self, req: PayoutRequest) -> ProviderResult:
        payload = {
            "amount": str(req.amount),
            "currency": req.currency,
            "to": normalize_phone(req.phone),
            "description": req.description,
            "external_reference": req.external_reference,
        }
        data = await self._call("POST", "withdraw/", payload)
        reference = data.get("reference")
        if not reference:
            raise ProviderUnavailable("campay withdraw response had no reference")
        return ProviderResult(
            reference=str(reference),
            status=map_status(data.get("status")) if data.get("status") else ProviderStatus.PENDING,
            operator=data.get("operator"),
            raw=data,
        )

    async def get_transaction(self, reference: str) -> ProviderTransaction:
        data = await self._call("GET", f"transaction/{reference}/")
        status = map_status(data.get("status"))
        return ProviderTransaction(
            reference=str(data.get("reference") or reference),
            status=status,
            external_reference=data.get("external_reference"),
            amount=_to_int(data.get("amount")),
            operator=data.get("operator"),
            failure_reason=_error_message(data) if status is ProviderStatus.FAILED else None,
            raw=data,
        )

    async def get_balance(self) -> ProviderBalance:
        data = await self._call("GET", "balance/")  # VERIFY path (SDKs differ: balance/ vs utilities/balance/)
        return ProviderBalance(
            total=_to_int(data.get("total_balance")) or 0,
            mtn=_to_int(data.get("mtn_balance")) or 0,
            orange=_to_int(data.get("orange_balance")) or 0,
            currency=str(data.get("currency") or "XAF"),
        )

    # ------------------------------------------------------------ webhook
    def verify_webhook(self, params: Mapping[str, str]) -> WebhookEvent:
        """Check the `signature` param. ASSUMPTION (VERIFY on demo): Campay sends the
        webhook as query params including `signature`, a JWT signed HS256 with our
        webhook key. The returned event is only a hint: re-fetch before crediting."""
        if not self._webhook_key:
            raise ProviderError("CAMPAY_WEBHOOK_KEY is not configured")
        signature = params.get("signature")
        if not signature:
            raise ProviderError("missing webhook signature")
        try:
            jwt.decode(signature, self._webhook_key, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise ProviderError("invalid webhook signature") from exc
        reference = params.get("reference")
        if not reference:
            raise ProviderError("webhook has no reference")
        return WebhookEvent(
            reference=reference,
            external_reference=params.get("external_reference"),
            status=map_status(params.get("status")),
            raw={k: v for k, v in params.items() if k != "signature"},
        )
