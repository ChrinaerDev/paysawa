"""The demo merchant's own logic: local records of deposits, withdrawals and payment links, kept in step
with Paysawa through polling AND webhooks. Framework-free so it can be tested without a server."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from merchant_app.paysawa_client import PaysawaClient, PaysawaError

FINAL = ("SUCCESSFUL", "FAILED")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path
        self.records: dict[str, dict] = {}
        if path and path.exists():
            try:
                self.records = {r["id"]: r for r in json.loads(path.read_text())}
            except (OSError, ValueError, KeyError):
                self.records = {}

    def save(self) -> None:
        if self.path:
            try:
                self.path.write_text(json.dumps(list(self.records.values()), indent=1))
            except OSError:
                pass

    def add(self, record: dict) -> dict:
        self.records[record["id"]] = record
        self.save()
        return record

    def all(self) -> list[dict]:
        return sorted(self.records.values(), key=lambda r: r["created_at"], reverse=True)

    def by_external(self, external_reference: str | None) -> dict | None:
        return next((r for r in self.records.values() if external_reference and r["external_reference"] == external_reference), None)


class MerchantService:
    def __init__(self, client: PaysawaClient, store: Store, public_url: str = ""):
        self.client = client
        self.store = store
        self.public_url = public_url.rstrip("/")
        self.webhook_log: deque = deque(maxlen=50)
        self._tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------ records
    def _new(self, kind: str, amount: int, phone: str | None, description: str, external_reference: str, reference: str,
             status: str, operator: str | None = None, link: str | None = None, ussd: str | None = None, note: str | None = None) -> dict:
        ts = now()
        record = {"id": uuid.uuid4().hex[:12], "kind": kind, "amount": amount, "phone": phone, "description": description,
                  "external_reference": external_reference, "reference": reference, "status": status, "operator": operator,
                  "link": link, "ussd_code": ussd, "note": note, "created_at": ts, "updated_at": ts}
        return self.store.add(record)

    # ------------------------------------------------------------ actions
    async def deposit(self, amount: int, phone: str, description: str = "") -> dict:
        external = f"dep-{uuid.uuid4().hex[:10]}"
        result = await self.client.collect(amount, phone, description or "Deposit", external)
        record = self._new("deposit", amount, phone, description, external, result["reference"], (result.get("status") or "PENDING").upper(),
                           operator=result.get("operator"), ussd=result.get("ussd_code"))
        self._watch_if_pending(record)
        return record

    async def withdraw(self, amount: int, phone: str, description: str = "") -> dict:
        external = f"wd-{uuid.uuid4().hex[:10]}"
        result = await self.client.withdraw(amount, phone, description or "Withdrawal", external)
        record = self._new("withdrawal", amount, phone, description, external, result["reference"], (result.get("status") or "PENDING").upper(),
                           operator=result.get("operator"))
        self._watch_if_pending(record)
        return record

    async def payment_link(self, amount: int, description: str = "", redirect: bool = True) -> dict:
        external = f"lnk-{uuid.uuid4().hex[:10]}"
        redirect_url = f"{self.public_url}/thanks" if redirect and self.public_url else None
        note = None
        try:
            result = await self.client.payment_link(amount, description or "Payment", external, redirect_url)
        except PaysawaError as exc:
            if redirect_url and exc.code in ("invalid_redirect_url", "invalid_url"):
                # live links need a public https redirect; a localhost demo cannot have one
                note = "No redirect after payment (live mode needs a public https redirect URL)."
                result = await self.client.payment_link(amount, description or "Payment", external, None)
            else:
                raise
        record = self._new("payment_link", amount, None, description, external, result["reference"], "PENDING", link=result["link"], note=note)
        self._watch_if_pending(record)
        return record

    # ------------------------------------------------------------ keeping in step with Paysawa
    def _apply(self, record: dict, status: str | None, operator: str | None = None, from_webhook: bool = False) -> None:
        status = (status or "").upper() or record["status"]
        if record["kind"] == "payment_link" and from_webhook and status == "FAILED":
            record["note"] = "A payment attempt failed, the link is still open."  # the customer can retry on the same link
        else:
            record["status"] = status
        if operator:
            record["operator"] = operator
        record["updated_at"] = now()
        self.store.save()

    async def refresh(self, record_id: str) -> dict:
        record = self.store.records[record_id]
        if record["status"] in FINAL:
            return record
        info = await self.client.transaction(record["reference"])
        self._apply(record, info.get("status"), info.get("operator"))
        return record

    async def refresh_pending(self, limit: int = 10) -> None:
        for record in [r for r in self.store.all() if r["status"] not in FINAL][:limit]:
            try:
                await self.refresh(record["id"])
            except PaysawaError:
                pass

    def _watch_if_pending(self, record: dict) -> None:
        if record["status"] in FINAL:
            return
        task = asyncio.create_task(self._watch(record["id"]))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _watch(self, record_id: str, max_seconds: int = 300) -> None:
        """Polls Paysawa for one pending record: works even when Paysawa cannot reach our webhook URL (localhost)."""
        started = time.monotonic()
        while time.monotonic() - started < max_seconds:
            await asyncio.sleep(3 if time.monotonic() - started < 60 else 10)
            record = self.store.records.get(record_id)
            if record is None or record["status"] in FINAL:
                return
            try:
                await self.refresh(record_id)
            except PaysawaError:
                pass

    async def handle_webhook(self, params: dict) -> dict:
        entry = {"time": now(), "valid": False, "summary": "", "params": {k: v for k, v in params.items() if k != "signature"}}
        try:
            verified = self.client.verify_webhook(params)
        except PaysawaError as exc:
            entry["summary"] = f"REJECTED: {exc.message}"
            self.webhook_log.appendleft(entry)
            raise
        entry["valid"] = True
        record = self.store.by_external(verified.get("external_reference"))
        if record is None:
            entry["summary"] = f"no local record for external_reference={verified.get('external_reference')!r}"
        elif str(verified.get("amount")) != str(record["amount"]):
            entry["summary"] = f"IGNORED: amount {verified.get('amount')} does not match our {record['amount']} for {record['id']}"
        else:
            self._apply(record, verified.get("status"), verified.get("operator"), from_webhook=True)
            entry["summary"] = f"{record['kind']} {record['id']} is now {record['status']}"
        self.webhook_log.appendleft(entry)
        return {"ok": True}
