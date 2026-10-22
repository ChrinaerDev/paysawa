# Paysawa

Paysawa is a payment gateway for **mobile money in Cameroon** (MTN Mobile Money and Orange Money, amounts in XAF).
With one integration you can **collect** money from customers, **withdraw** money to any MTN or Orange number,
share **payment links** and receive **webhooks** when something happens.

Base URL of the API: `https://paysawa.onrender.com`

## Three ways to integrate

| Way | You use | Best for |
|---|---|---|
| **Apps API** (`/api`) | App username, app password and webhook key | Server-to-server integrations with token authentication. Works with the [Python SDK](sdk-python.md). |
| **Paysawa API v1** (`/v1`) | Secret API key (`sk_test_...` / `sk_live_...`) | New JSON integrations with idempotency keys and richer objects. |
| **Hosted pay page** | A payment link | Getting paid without building a checkout page. |

All three move money in the same account and show up in the same transaction history.

## Core concepts

- **Test and live.** A *test* app or key uses the sandbox: nothing real is charged and results are instant and predictable
  (see [Test and live](environments.md)). A *live* app or key moves real money.
- **One balance.** Every merchant has a single balance. Collections add to it, withdrawals take from it. There is no split by operator.
- **Statuses.** The Apps API reports `PENDING`, `SUCCESSFUL` or `FAILED`. API v1 reports `pending`, `succeeded`, `failed` or `expired`.
- **Amounts** are whole XAF numbers, minimum 10.
- **Fees.** A collection credits you the amount minus Paysawa's fee; a withdrawal takes the amount plus the fee from your balance.
  The default fee is 2.5% and can differ per account.
- **Your own reference.** Send an `external_reference` (Apps API) or `merchant_reference` (v1) with every payment. It comes back in
  statuses and webhooks so you can match the payment to your order.

## Where to start

1. [Getting started](getting-started.md): from zero to a first payment in five minutes.
2. [Authentication](authentication.md): how tokens and keys work.
3. [Webhooks](webhooks.md): how Paysawa tells your server that a payment finished.
4. [Python SDK](sdk-python.md): `pip install paysawa`.
