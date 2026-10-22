---
id: webhooks
title: Webhooks
group: Webhooks
order: 1
---
# Webhooks

A webhook is Paysawa calling **your server** when a payment finishes, so you do not have to keep asking. There are two kinds.

| Kind | Belongs to | How it arrives |
|---|---|---|
| **App webhooks** | An app (username/password) | `GET` request to the app's webhook URL, data in the query string, signed with the app's webhook key |
| **API v1 webhooks** | An API key account (v1) | `POST` of a JSON body to a registered endpoint, signed with a signing secret in a header |

Always **verify the signature**, otherwise anyone who knows your URL could fake a payment.

## App webhooks

Set the app's webhook URL when you create it (`webhook_url`) or later with `PATCH /me/apps/{id}`.
An app only receives events for the payments made **through that app**, including payments made on its payment links.

Paysawa calls:

```
GET https://your-server.example.com/webhooks/paysawa
    ?status=SUCCESSFUL
    &reference=col_8f3a1c2d4e5f6a7b8c9d
    &amount=5000
    &currency=XAF
    &operator=MTN
    &code=
    &operator_reference=op-123
    &external_reference=order-1001
    &signature=eyJhbGciOiJIUzI1NiIs...
```

| Parameter | Meaning |
|---|---|
| `status` | `SUCCESSFUL`, `FAILED` or `PENDING` |
| `reference` | the Paysawa reference of the payment (`col_...` or `pay_...`) |
| `amount`, `currency` | amount in XAF, as text |
| `operator` | `MTN` or `ORANGE` when known |
| `external_reference` | **your** reference, as you sent it |
| `operator_reference` | the operator's own reference when available |
| `signature` | a JWT (HS256) signed with the app's **webhook key** over all the other parameters |

### Verify it

With the SDK:

```python
from paysawa import Client, WebhookVerificationError

client = Client.from_env()

@app.get("/webhooks/paysawa")                      # Flask
def paysawa_webhook():
    try:
        event = client.verify_webhook(request.args.to_dict())
    except WebhookVerificationError:
        return "invalid", 401
    order = find_order(event.external_reference)
    if event.is_successful and event.amount == order.total:
        mark_paid(order)
    return "ok"
```

Without the SDK, decode `signature` with your webhook key (HS256), then check that every signed field equals the received parameter:

```python
import jwt

def verify(params: dict, webhook_key: str) -> dict:
    signed = jwt.decode(params["signature"], webhook_key, algorithms=["HS256"])
    clean = {k: v for k, v in params.items() if k != "signature"}
    for key, value in signed.items():
        if key not in ("iat", "exp") and str(clean.get(key, "")) != str(value):
            raise ValueError(f"{key} was tampered with")
    return clean
```

```javascript
// Node.js with the "jsonwebtoken" package
const jwt = require("jsonwebtoken");
function verify(query, webhookKey) {
  const signed = jwt.verify(query.signature, webhookKey, { algorithms: ["HS256"] });
  for (const [k, v] of Object.entries(signed)) {
    if (k !== "iat" && k !== "exp" && String(query[k] ?? "") !== String(v)) throw new Error(k + " was tampered with");
  }
  const { signature, ...clean } = query;
  return clean;
}
```

### Delivery rules

- Answer with any **2xx** status to confirm. Anything else (or no answer within 8 seconds) is retried: up to 8 attempts, the first retry after about
  a minute, then doubling, never more than 6 hours apart.
- Webhooks can arrive **more than once**. Make your handler idempotent: if the order is already paid, do nothing and answer `200`.
- Do not rely on the webhook alone. If it never arrives, `GET /api/transaction/{reference}/` gives the truth.
- Live webhook URLs must be `https` and public. In test mode `http` is allowed; addresses on private networks are always refused.

## API v1 webhooks

Register an endpoint with `POST /me/webhook-endpoints` (`{"mode": "live", "url": "https://...", "events": []}`, empty `events` means all).
Events: `collection.succeeded`, `collection.failed`, `collection.expired`, `payout.succeeded`, `payout.failed`.

```json
{
  "id": "evt_1f2e3d4c5b6a7988",
  "type": "collection.succeeded",
  "created": "2026-10-18T09:15:02.456789+00:00",
  "data": { "id": "col_8f3a1c2d4e5f6a7b8c9d", "object": "collection", "status": "succeeded", "amount": 5000, "fee": 125, "...": "..." }
}
```

Headers: `X-Paysawa-Signature: t=<unix time>,v1=<hex>`, `X-Paysawa-Event`, `X-Paysawa-Delivery`.
The signature is an HMAC-SHA256 of `"<t>.<raw request body>"` with your endpoint's signing secret. Reject it if `t` is older than 5 minutes.

```python
import hmac, hashlib, time

def verify(secret: str, raw_body: bytes, header: str) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(","))
    if abs(time.time() - int(parts["t"])) > 300:
        return False
    expected = hmac.new(secret.encode(), f"{parts['t']}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])
```

Reply with any 2xx. Failed deliveries are retried with the same schedule as above and can be inspected with `GET /me/webhook-deliveries`.
