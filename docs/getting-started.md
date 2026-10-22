# Getting started

This walkthrough uses the **sandbox**, so nothing real is charged.

## 1. Create your account

```bash
curl -X POST https://paysawa.onrender.com/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name": "Ada Labs", "email": "ada@example.com", "password": "a-long-password"}'
```

The answer contains a `token` for the dashboard API. Keep it for the next step (it is valid for 12 hours; sign in again with `POST /auth/login`).

## 2. Create an app and get its credentials

An **app** represents your application on Paysawa: it gives you an **app username**, an **app password** and a **webhook key**.

```bash
curl -X POST https://paysawa.onrender.com/me/apps \
  -H "Authorization: Bearer DASHBOARD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My shop", "mode": "test", "webhook_url": "https://example.com/webhooks/paysawa"}'
```

You can read the credentials again at any time (a dashboard shows them behind a show/hide toggle):

```bash
curl https://paysawa.onrender.com/me/apps/APP_ID/credentials -H "Authorization: Bearer DASHBOARD_TOKEN"
```

```json
{
  "username": "pa_1a2b3c4d5e6f7a8b",
  "password": "k3J...43 characters...",
  "webhook_key": "whk_Qe9...",
  "api_base_url": "https://paysawa.onrender.com/api/"
}
```

> **Keep the password and the webhook key on your server.** Never put them in a mobile app, a web page or a git repository.

## 3. Get an access token

```bash
curl -X POST https://paysawa.onrender.com/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "pa_1a2b3c4d5e6f7a8b", "password": "YOUR_APP_PASSWORD"}'
```

```json
{ "token": "eyJhbGciOi...", "expires_in": 3600 }
```

## 4. Collect your first payment

```bash
curl -X POST https://paysawa.onrender.com/api/collect/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": "5000", "currency": "XAF", "from": "670000001", "description": "Order 1001", "external_reference": "order-1001"}'
```

```json
{ "reference": "col_8f3a1c2d4e5f6a7b8c9d", "ussd_code": "*126#", "operator": "MTN", "status": "SUCCESSFUL" }
```

In the sandbox the result is instant. With a **live** app the status starts as `PENDING`: the customer receives a prompt on their phone and
confirms with their PIN. See [Test and live](environments.md) for the sandbox phone numbers.

## 5. Check the result

```bash
curl https://paysawa.onrender.com/api/transaction/col_8f3a1c2d4e5f6a7b8c9d/ -H "Authorization: Token YOUR_TOKEN"
```

Or let Paysawa tell you: set a webhook URL on your app and read [Webhooks](webhooks.md).

## 6. Pay money out

```bash
curl -X POST https://paysawa.onrender.com/api/withdraw/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": "1000", "currency": "XAF", "to": "690000001", "description": "Refund", "external_reference": "refund-1001"}'
```

## Or use the SDK

```bash
pip install paysawa
```

```python
from paysawa import Client

client = Client("pa_1a2b3c4d5e6f7a8b", "YOUR_APP_PASSWORD", "whk_...", base_url="https://paysawa.onrender.com/api/")
tx = client.collect(5000, "670000001", "Order 1001", "order-1001", wait=True)
print(tx.status)
```

The full SDK guide is in [Python SDK](sdk-python.md).
