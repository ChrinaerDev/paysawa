---
id: pay-page
title: Hosted pay page
group: Payment links
order: 1
---
# Hosted pay page

The hosted pay page lets you get paid without building a checkout: you create a link, your customer opens it, enters their MTN or Orange number,
approves on their phone and is sent back to your site. The page is mobile friendly, in English or French (automatic, with a switch), and allows
**3 attempts** per link.

## Create a link

Apps API:

```bash
curl -X POST {{BASE_URL}}/api/get_payment_link/ \
  -H "Authorization: Token YOUR_TOKEN" -H "Content-Type: application/json" \
  -d '{"amount": "2000", "currency": "XAF", "description": "Order 1002", "external_reference": "order-1002", "redirect_url": "https://shop.example.com/thanks"}'
```

API v1 (also lets you choose how long the link lives, 1 to 1440 minutes):

```bash
curl -X POST {{BASE_URL}}/v1/checkout-sessions \
  -H "Authorization: Bearer sk_test_..." -H "Content-Type: application/json" \
  -d '{"amount": 2000, "description": "Order 1002", "merchant_reference": "order-1002", "redirect_url": "https://shop.example.com/thanks", "expires_in_minutes": 60}'
```

Send the returned `link` (or `url`) to your customer. Links last 60 minutes unless you choose otherwise. Times are in UTC; use `expires_in_seconds` for countdowns.

After a successful payment the page offers a **Return** button and redirects automatically after a few seconds to your `redirect_url`
(`https` and public in live mode). Your server learns about the payment by [webhook](#/webhooks): the event carries your reference
(`external_reference` / `merchant_reference`), so match the order on that, not on the redirect.

## Check a link

`GET /api/transaction/{reference}/` with the link's reference (`cs_...`) answers `PENDING` (open), `SUCCESSFUL` (paid) or `FAILED` (expired);
when paid it also returns `payment_reference`, the reference of the payment itself. With API v1 use `GET /v1/checkout-sessions/{id}`.

## Build your own checkout page

You can replace the hosted page with your own. It needs three **public** endpoints (no credentials, CORS enabled), keyed by the link's id:

| Call | Purpose |
|---|---|
| `GET /gate/sessions/{id}` | merchant name, amount, description, `status` (`open`, `paid`, `expired`), `attempts_left`, `expires_in_seconds`, and `payment` (the latest attempt) |
| `POST /gate/sessions/{id}/pay` with `{"phone": "6XXXXXXXX"}` | start the payment: the customer gets a prompt |
| `GET /gate/sessions/{id}/status` | poll every 2 to 3 seconds while the customer approves |

`payment.status` is `pending`, `succeeded` or `failed` (with a `failure_message`). When `status` becomes `paid` the answer includes `redirect_url`.
Errors you should handle: `already_paid`, `session_expired`, `too_many_attempts`, `payment_in_progress`, `invalid_phone`, `rate_limited`.
