---
id: errors
title: Errors
group: Reference
order: 1
---
# Errors

## Shape

The Apps API (`/api`) answers errors like this:

```json
{ "message": "Available balance is 0 XAF, 1025 XAF needed (amount + fee).", "code": "insufficient_funds" }
```

API v1 and the dashboard API wrap the same two fields:

```json
{ "error": { "code": "insufficient_funds", "message": "Available balance is 0 XAF, 1025 XAF needed (amount + fee)." } }
```

Use the HTTP status to decide *what kind* of problem it is and `code` to decide *what to do*. `message` is for humans.

## Codes

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `invalid_amount` | the amount is not a whole positive number of XAF |
| 400 | `invalid_currency` | only `XAF` is supported |
| 401 | `unauthorized` | missing, invalid or expired token / key |
| 401 | `invalid_credentials` | wrong app username or password |
| 402 | `insufficient_funds` | a withdrawal needs more than your available balance (amount + fee) |
| 403 | `live_not_enabled` | live mode is not enabled for your account yet |
| 403 | `account_suspended` | your account cannot make payments |
| 404 | `not_found` | unknown reference or id |
| 409 | `idempotency_conflict` | the same `Idempotency-Key` was used with different parameters (v1) |
| 409 | `payment_in_progress` | a payment on this link is already waiting for the customer |
| 409 | `already_paid` | the link is already paid |
| 410 | `session_expired` | the payment link expired |
| 422 | `invalid_phone` | not a Cameroonian mobile number |
| 422 | `amount_too_small` | below the 10 XAF minimum |
| 422 | `amount_too_large` | above your per-transaction limit |
| 422 | `daily_limit_exceeded` | above your daily limit |
| 422 | `invalid_request` | a required field is missing or malformed |
| 422 | `invalid_redirect_url` / `invalid_url` | redirect or webhook URL refused (must be public, https in live) |
| 429 | `rate_limited` / `too_many_attempts` | slow down |
| 503 | `provider_unavailable` | the mobile money operator side is unavailable, try again shortly |
| 503 | `busy` / `db_timeout` | Paysawa is busy: retry reads; for a payment, check it before retrying |
| 500 | `internal_error` | unexpected problem on our side |

## Payments that fail later

A request can succeed (`200`) and the payment still end as `FAILED`: the customer refused, had no funds, or did nothing. The `reason`
field of the transaction explains it. A failed **withdrawal** returns the held money to your balance automatically.

## If a payment request fails with a network error or 5xx

Do not send it again blindly: you may charge the customer twice. First look the payment up by the `external_reference` you sent
(keep your own record of it), and only retry if it does not exist.
