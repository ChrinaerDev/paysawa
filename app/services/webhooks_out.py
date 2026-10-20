"""Outgoing merchant webhooks. webhook_deliveries is the queue (polled with SKIP LOCKED).

Two styles of endpoint:
  * "paysawa": JSON POST, header X-Paysawa-Signature (HMAC-SHA256)
  * "campay":  GET with Campay-style query parameters and a `signature` JWT signed with the app's webhook key
               (so code written for Campay's webhooks works unchanged against Paysawa)
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Transaction, WebhookDelivery, WebhookEndpoint
from app.netsafety import UnsafeUrl, check_public_url
from app.security import derive_app_webhook_key, sign_callback, sign_payload
from app.services.compat import campay_params
from app.services.serializers import tx_to_dict

logger = logging.getLogger("paysawa.webhooks")

EVENT_TYPES = (
    "collection.succeeded",
    "collection.failed",
    "collection.expired",
    "payout.succeeded",
    "payout.failed",
)
MAX_ATTEMPTS = 8


async def enqueue_event(session: AsyncSession, tx: Transaction, event_type: str) -> int:
    endpoints = (
        await session.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.merchant_id == tx.merchant_id,
                WebhookEndpoint.mode == tx.mode,
                WebhookEndpoint.is_active.is_(True),
            )
        )
    ).scalars().all()
    count = 0
    for endpoint in endpoints:
        if endpoint.style == "campay":
            # a Campay-style endpoint belongs to one app and only hears about that app's transactions
            if (tx.meta or {}).get("app_id") != str(endpoint.app_id):
                continue
            payload = {"style": "campay", "params": campay_params(tx)}
        else:
            if endpoint.events and event_type not in endpoint.events:
                continue
            payload = {
                "id": f"evt_{secrets.token_hex(8)}",
                "type": event_type,
                "created": datetime.now(timezone.utc).isoformat(),
                "data": tx_to_dict(tx),
            }
        session.add(WebhookDelivery(endpoint_id=endpoint.id, transaction_id=tx.id, event_type=event_type, payload=payload))
        count += 1
    return count


async def deliver_due(session: AsyncSession, http: httpx.AsyncClient, limit: int = 20) -> dict:
    rows = (
        await session.execute(
            select(WebhookDelivery)
            .where(WebhookDelivery.status == "pending", WebhookDelivery.next_attempt_at <= func.now())
            .order_by(WebhookDelivery.next_attempt_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    if not rows:
        return {"attempted": 0, "delivered": 0, "failed": 0}

    endpoint_ids = {row.endpoint_id for row in rows}
    endpoints = {
        e.id: e
        for e in (await session.execute(select(WebhookEndpoint).where(WebhookEndpoint.id.in_(endpoint_ids)))).scalars()
    }

    async def send(delivery: WebhookDelivery):
        endpoint = endpoints.get(delivery.endpoint_id)
        if endpoint is None or not endpoint.is_active:
            return delivery, False, None, "endpoint inactive", True
        settings = get_settings()
        try:
            await asyncio.to_thread(
                check_public_url, endpoint.url, allow_http=endpoint.mode == "test",
                allow_private=endpoint.mode == "test" and settings.allow_private_webhook_urls,
            )
        except UnsafeUrl as exc:
            return delivery, False, None, f"unsafe url: {exc}", False
        try:
            if endpoint.style == "campay":
                params = dict(delivery.payload.get("params", {}))
                key = derive_app_webhook_key(endpoint.app_id, settings.key_secret)
                params["signature"] = sign_callback(key, {k: v for k, v in params.items()})
                response = await http.get(endpoint.url, params=params, headers={"User-Agent": "Paysawa-Webhooks/1"})
            else:
                body = json.dumps(delivery.payload, separators=(",", ":")).encode()
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Paysawa-Webhooks/1",
                    "X-Paysawa-Signature": sign_payload(endpoint.signing_secret, body, int(time.time())),
                    "X-Paysawa-Event": delivery.event_type,
                    "X-Paysawa-Delivery": str(delivery.id),
                }
                response = await http.post(endpoint.url, content=body, headers=headers)
        except httpx.HTTPError as exc:
            return delivery, False, None, type(exc).__name__, False
        ok = 200 <= response.status_code < 300
        return delivery, ok, response.status_code, None if ok else f"HTTP {response.status_code}", False

    results = await asyncio.gather(*(send(d) for d in rows))
    now = datetime.now(timezone.utc)
    delivered = failed = 0
    for delivery, ok, status_code, error, give_up in results:
        delivery.attempts += 1
        delivery.last_status_code = status_code
        delivery.last_error = error
        if ok:
            delivery.status = "delivered"
            delivery.delivered_at = now
            delivered += 1
        elif give_up or delivery.attempts >= MAX_ATTEMPTS:
            delivery.status = "failed"
            failed += 1
        else:
            delivery.next_attempt_at = now + timedelta(seconds=min(60 * 2 ** (delivery.attempts - 1), 6 * 3600))
    await session.commit()
    return {"attempted": len(rows), "delivered": delivered, "failed": failed}
