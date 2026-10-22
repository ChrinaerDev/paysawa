---
id: authentication
title: Authentication
group: Introduction
order: 3
---
# Authentication

Paysawa has three kinds of credentials. Use the one that matches the API you call.

| Credential | Used for | Sent as |
|---|---|---|
| App username + password | The Apps API (`/api/...`) | You exchange them for a token, then send `Authorization: Token <token>` |
| Secret API key | API v1 (`/v1/...`) | `Authorization: Bearer sk_test_...` or `sk_live_...` |
| Dashboard token | Managing your account (`/me/...`) | `Authorization: Bearer <token>` from `POST /auth/login` |

## Apps API tokens

1. `POST {{BASE_URL}}/api/token/` with your app `username` and `password`.
2. You get a `token` valid for `expires_in` seconds (3600, one hour).
3. Send it on every call: `Authorization: Token <token>` (the word `Bearer` is accepted too).
4. When a call answers `401`, request a new token and retry. The [SDK](#/sdk-python) does all of this for you.

Reuse a token for its whole lifetime instead of asking for a new one before every call. Token requests are limited to 20 per 5 minutes per
username and address.

## API keys

Create keys in your dashboard (or with `POST /me/api-keys`). A key starts with `sk_test_` (sandbox) or `sk_live_` (real money); **the key decides the
mode**. You can show a key again at any time. Revoke a key if it leaks: calls with it stop immediately.

## Apps and mode

An app is created for one mode, `test` or `live`. Test and live have separate balances, transactions, keys, apps and webhooks.
A live app only works once Paysawa has enabled live mode on your account.
