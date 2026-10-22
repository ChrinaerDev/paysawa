"""Minimal Paysawa client for the apps API. Standalone: only httpx and PyJWT.

    client = PaysawaClient(base_url="https://your-paysawa/api/", username="pa_...", password="...", webhook_key="whk_...")
    ref = await client.collect(5000, "670000001", "Order 1001", "order-1001")   # customer gets a prompt
    info = await client.transaction(ref["reference"])                            # PENDING | SUCCESSFUL | FAILED
    await client.withdraw(1000, "690000001", "Refund", "refund-1001")
    link = await client.payment_link(2000, "Order 1002", "order-1002", "https://shop.example.com/thanks")
"""
from __future__ import annotations

import time

import httpx
import jwt


class PaysawaError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class PaysawaClient:
    def __init__(self, base_url: str, username: str, password: str, webhook_key: str = "",
                 client: httpx.AsyncClient | None = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/") + "/"
        self.username = username
        self.password = password
        self.webhook_key = webhook_key
        self._owns_client = client is None
        self._http = client or httpx.AsyncClient(timeout=timeout)
        self._token: str | None = None
        self._expires_at = 0.0

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    # ------------------------------------------------------------ transport
    @staticmethod
    def _raise(response: httpx.Response) -> None:
        try:
            data = response.json()
        except ValueError:
            data = {}
        data = data if isinstance(data, dict) else {}
        raise PaysawaError(response.status_code, str(data.get("code") or "http_error"), str(data.get("message") or f"HTTP {response.status_code}"))

    async def _send(self, method: str, url: str, json=None, headers: dict | None = None) -> httpx.Response:
        try:
            return await self._http.request(method, url, json=json, headers=headers or {})
        except httpx.TimeoutException:
            raise PaysawaError(0, "timeout", "Paysawa did not answer in time.")
        except httpx.HTTPError:
            raise PaysawaError(0, "unreachable", f"Cannot reach Paysawa at {self.base_url}.")

    async def _get_token(self, force: bool = False) -> str:
        if not force and self._token and time.monotonic() < self._expires_at:
            return self._token
        response = await self._send("POST", self.base_url + "token/", json={"username": self.username, "password": self.password})
        if response.status_code >= 400:
            self._raise(response)
        data = response.json()
        self._token = data["token"]
        self._expires_at = time.monotonic() + max(int(data.get("expires_in") or 300) - 30, 10)
        return self._token

    async def _call(self, method: str, path: str, json=None) -> dict:
        for attempt in (0, 1):
            token = await self._get_token(force=attempt == 1)
            response = await self._send(method, self.base_url + path, json=json, headers={"Authorization": f"Token {token}"})
            if response.status_code == 401 and attempt == 0:
                continue  # expired token: get a new one and retry once
            if response.status_code >= 400:
                self._raise(response)
            return response.json()
        raise PaysawaError(401, "unauthorized", "Could not authenticate with Paysawa.")

    # ------------------------------------------------------------ API
    async def collect(self, amount: int, phone: str, description: str = "", external_reference: str | None = None, currency: str = "XAF") -> dict:
        return await self._call("POST", "collect/", {"amount": str(amount), "currency": currency, "from": phone,
                                                     "description": description, "external_reference": external_reference})

    async def withdraw(self, amount: int, phone: str, description: str = "", external_reference: str | None = None, currency: str = "XAF") -> dict:
        return await self._call("POST", "withdraw/", {"amount": str(amount), "currency": currency, "to": phone,
                                                      "description": description, "external_reference": external_reference})

    async def transaction(self, reference: str) -> dict:
        return await self._call("GET", f"transaction/{reference}/")

    async def balance(self) -> dict:
        return await self._call("GET", "balance/")

    async def payment_link(self, amount: int, description: str = "", external_reference: str | None = None,
                           redirect_url: str | None = None, currency: str = "XAF") -> dict:
        body = {"amount": str(amount), "currency": currency, "description": description, "external_reference": external_reference}
        if redirect_url:
            body["redirect_url"] = redirect_url
        return await self._call("POST", "get_payment_link/", body)

    # ------------------------------------------------------------ webhooks
    def verify_webhook(self, params: dict) -> dict:
        """Checks the `signature` of a Paysawa webhook (query parameters). Returns the parameters without it.
        Also compares every signed field with the received one, so a valid signature cannot be reused with other values."""
        if not self.webhook_key:
            raise PaysawaError(0, "no_webhook_key", "PAYSAWA_WEBHOOK_KEY is not configured.")
        signature = params.get("signature")
        if not signature:
            raise PaysawaError(401, "missing_signature", "The webhook has no signature.")
        try:
            signed = jwt.decode(signature, self.webhook_key, algorithms=["HS256"])
        except jwt.PyJWTError:
            raise PaysawaError(401, "invalid_signature", "The webhook signature is not valid for this webhook key.")
        clean = {k: v for k, v in params.items() if k != "signature"}
        for key, value in signed.items():
            if key in ("iat", "exp"):
                continue
            if str(clean.get(key, "")) != str(value):
                raise PaysawaError(401, "tampered", f"Parameter '{key}' does not match what was signed.")
        return clean
