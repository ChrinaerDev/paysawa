---
id: dashboard-api
title: Dashboard API
group: Reference
order: 4
---
# Dashboard API

The endpoints a dashboard uses to manage an account. Authenticate with the token from `POST /auth/login` or `POST /auth/signup`:
`Authorization: Bearer <token>` (valid for 12 hours).

| Method and path | Purpose |
|---|---|
| `POST /auth/signup` | `{name, email, password}` creates an account (starts in test mode) and returns `{token, merchant}` |
| `POST /auth/login` | `{email, password}` returns `{token, merchant}` |
| `GET /me` | the account: limits, fees, whether live mode is enabled |
| `GET /me/balance` | balances for test and live: `{test: {available, held}, live: {available, held}}` |
| `GET /me/transactions?mode=&type=&status=&limit=&offset=` | transaction history |
| `POST /me/api-keys` | `{mode, label}` creates a secret key |
| `GET /me/api-keys` | list keys (`prefix`, `revealable`, `last_used_at`...) |
| `GET /me/api-keys/{id}/secret` | show a key again (backs a show/hide toggle) |
| `DELETE /me/api-keys/{id}` | revoke a key |
| `POST /me/apps` | `{name, mode, webhook_url?}` creates an app |
| `GET /me/apps` | list apps |
| `GET /me/apps/{id}/credentials` | `{username, password, webhook_key, api_base_url}` |
| `PATCH /me/apps/{id}` | change `name` or `webhook_url` (empty string removes the webhook) |
| `DELETE /me/apps/{id}` | revoke an app |
| `POST /me/webhook-endpoints` | `{mode, url, events}` registers an API v1 webhook endpoint; returns `signing_secret` |
| `GET /me/webhook-endpoints`, `GET /me/webhook-endpoints/{id}/secret`, `DELETE /me/webhook-endpoints/{id}` | list, show the signing secret, delete |
| `GET /me/webhook-deliveries` | recent webhook deliveries and their results |

Signing up is rate limited, and so are login attempts.
