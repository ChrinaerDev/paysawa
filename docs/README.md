# Paysawa documentation

Version 0.1.1. Base URL: `https://paysawa.onrender.com`. A browsable version is in `docs_site/index.html`.

Français : [fr/README.md](fr/README.md)

## Introduction

- [Overview](overview.md)
- [Getting started](getting-started.md)
- [Authentication](authentication.md)
- [Test and live](environments.md)

## Apps API

- [Get a token (`POST /api/token/`)](api/token.md)
- [Collect (deposit) (`POST /api/collect/`)](api/collect.md)
- [Withdraw (payout) (`POST /api/withdraw/`)](api/withdraw.md)
- [Transaction status (`GET /api/transaction/{reference}/`)](api/transaction.md)
- [Balance (`GET /api/balance/`)](api/balance.md)
- [Payment link (`POST /api/get_payment_link/`)](api/get-payment-link.md)

## API v1

- [Create a collection (`POST /v1/collections`)](api/v1-create-collection.md)
- [Get a collection (`GET /v1/collections/{id}`)](api/v1-get-collection.md)
- [Create a payout (`POST /v1/payouts`)](api/v1-create-payout.md)
- [Get a payout (`GET /v1/payouts/{id}`)](api/v1-get-payout.md)
- [Balance (`GET /v1/balance`)](api/v1-balance.md)
- [List transactions (`GET /v1/transactions`)](api/v1-list-transactions.md)
- [Create a checkout session (`POST /v1/checkout-sessions`)](api/v1-create-checkout-session.md)
- [Get a checkout session (`GET /v1/checkout-sessions/{id}`)](api/v1-get-checkout-session.md)

## Webhooks

- [Webhooks](webhooks.md)

## Payment links

- [Hosted pay page](pay-page.md)

## SDKs

- [Python SDK](sdk-python.md)

## Reference

- [Errors](errors.md)
- [Going live](going-live.md)
- [FAQ](faq.md)
- [Dashboard API](dashboard-api.md)
