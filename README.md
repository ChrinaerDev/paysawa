# Paysawa gateway (backend)

A payment API built on top of one Campay account. Merchants get their own API keys, a sandbox,
webhooks and a hosted pay page; every collection and payout runs through **our** Campay credentials,
while an internal double-entry ledger tracks what each merchant owns (one accumulated balance per merchant,
not split by operator). Deposits and withdrawals work for any MTN or Orange Cameroon number.

> Status: backend feature-complete for a first release. Not yet run against real Neon/Campay by the author
> of this code: follow sections 3, 4 and 10 and report anything that fails. The only pieces still to build are the
> frontends (dashboard and the hosted pay page, see section 9).

## 1. Prerequisites

Python 3.11+, a Neon project, and (for live mode) your Campay production app credentials.

## 2. Database (Neon)

1. Create a Neon branch for development (keep `main` for production).
2. In the Neon SQL editor run, in this order: `schema.sql`, then `schema_002_checkout_sessions.sql`, then `schema_003_apps.sql`.
3. Copy the **pooled** connection string (host contains `-pooler`). You will paste it as `DATABASE_URL`.

## 3. Local setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # then edit .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # run twice: JWT_SECRET and INTERNAL_TICK_SECRET
python -m scripts.bootstrap                             # verifies schema, seeds the 4 platform ledger accounts
uvicorn app.main:app --reload
```

Check it works (replace the secret with your `INTERNAL_TICK_SECRET`):

```bash
curl localhost:8000/health
curl -H "X-Internal-Secret: <INTERNAL_TICK_SECRET>" localhost:8000/internal/db-check
# expected: "platform_accounts_seeded": true, "migration_002_applied": true and "migration_003_applied": true
```

Interactive API docs are served at `http://localhost:8000/docs`.

## 4. Test mode = built-in sandbox

Keys starting with `sk_test_` use a **simulated provider** (no external calls, no real money) and settle instantly.
The last digits of the phone number decide the outcome:

| Number ends with | Result |
|---|---|
| `0000` | fails |
| `9999` | stays pending forever |
| anything else | succeeds |

Valid formats: `6XXXXXXXX`, `+2376XXXXXXXX`, `2376XXXXXXXX`. Run the end-to-end check:

```bash
BASE_URL=http://localhost:8000 python -m scripts.smoke_test
```

To use Campay's demo environment instead, set `TEST_PROVIDER=campay_demo` and the `CAMPAY_DEMO_*` variables.

Extended checks (outgoing webhooks and their signature, failed-payout refund, retry queue, tick job). They need the server
started with `ALLOW_PRIVATE_WEBHOOK_URLS=true` in `.env` (dev only: lets test-mode webhooks target localhost) and
`INTERNAL_TICK_SECRET` set:

```bash
BASE_URL=http://localhost:8000 python -m scripts.smoke_test_extended
BASE_URL=http://localhost:8000 python -m scripts.smoke_test_extended --wait-retry   # also proves the tick retries (~65 s)
```

## 5. The CLI: the whole app in a terminal

A menu-driven client that talks to the HTTP API only (never the database). It covers signup/login, deposits (collections), withdrawals (payouts), balances and history, API keys and other credentials with a show/hide toggle, webhooks (including a built-in listener that verifies signatures), checkout sessions (you can play the customer), a sandbox lab with guided scenarios, and a checklist that always tells you what to test next.

```bash
pip install -r cli/requirements.txt
python -m cli                  # server defaults to http://localhost:8000
PAYSAWA_URL=https://your-app.onrender.com python -m cli
```

Only your server URL, login token and checklist progress are saved (in `~/.paysawa/cli.json`). No API key is stored there: the CLI fetches your key from the server when needed. Menu 8 switches TEST/LIVE; every LIVE money action needs you to type `LIVE`.

**Keys are revealable.** Both test and live keys can be shown again at any time (menu 4, or `GET /me/api-keys/{id}/secret` with your dashboard login), the way Campay shows its credentials. They are derived from a server secret (`API_KEY_SECRET`, defaults to `JWT_SECRET`) so only their hashes are stored in the database. **Never change that secret after keys exist**: old keys keep working but can no longer be revealed. Anyone with a merchant's dashboard login can see its live key, so protect that login.

## 6. Create accounts programmatically (no frontend needed)

### A. Admin CLI (talks to the database directly)

```bash
python -m scripts.admin create-merchant --name "Ada Labs" --email ada@example.com --password 'S3cret-pass' --with-test-key
python -m scripts.admin create-key      --email ada@example.com --mode test --label dev
python -m scripts.admin credit-test     --email ada@example.com --amount 100000     # sandbox money for testing payouts
python -m scripts.admin enable-live     --email ada@example.com --per-txn 50000 --daily 200000
python -m scripts.admin set-fees        --email ada@example.com --collection-bps 250 --payout-bps 250
python -m scripts.admin suspend         --email ada@example.com                      # or: activate
```

### B. HTTP API (what the future signup page will call)

```bash
BASE=http://localhost:8000

# 1) signup -> returns a dashboard JWT
curl -s $BASE/auth/signup -H 'Content-Type: application/json' \
  -d '{"name":"Ada Labs","email":"ada@example.com","password":"S3cret-pass"}'

# 2) login (later) -> JWT
curl -s $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.com","password":"S3cret-pass"}'

# 3) create an API key (you can reveal it again anytime: GET /me/api-keys/{id}/secret)
curl -s $BASE/me/api-keys -H "Authorization: Bearer <JWT>" -H 'Content-Type: application/json' \
  -d '{"mode":"test","label":"dev"}'

# 4) collect money (customer receives a prompt on their phone)
curl -s $BASE/v1/collections -H "Authorization: Bearer sk_test_..." -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: order-1001' \
  -d '{"amount":5000,"phone":"670000001","description":"Order 1001","merchant_reference":"1001"}'

# 5) pay out from the merchant balance (any MTN/Orange number)
curl -s $BASE/v1/payouts -H "Authorization: Bearer sk_test_..." -H 'Content-Type: application/json' \
  -d '{"amount":1000,"phone":"690000001","description":"Refund"}'

# 6) balance and history
curl -s $BASE/v1/balance      -H "Authorization: Bearer sk_test_..."
curl -s $BASE/v1/transactions -H "Authorization: Bearer sk_test_..."
```

Money rules: a collection credits the merchant `amount - fee`; a payout debits `amount + fee` (held first, released
if the payout fails). Defaults: 2.5% fee (250 bps), minimum amount 10 XAF.

## 7. Going live (real money)

1. Put your Campay **production** credentials in `.env`: `CAMPAY_LIVE_USERNAME`, `CAMPAY_LIVE_PASSWORD`, `CAMPAY_LIVE_WEBHOOK_KEY`.
2. In the Campay app settings: enable API withdrawals, and set the webhook URL to `<APP_BASE_URL>/webhooks/campay`.
3. Verify credentials: `curl -H "X-Internal-Secret: ..." "localhost:8000/internal/provider-check?mode=live"` (returns your Campay balances).
4. Enable live per merchant (CLI above). Live starts with low limits (50 000 XAF per transaction, 200 000 per day). Raise them per merchant as you gain trust.
5. Make one small real collection and one small real payout yourself first.

How live payments settle: Campay's webhook (needs a public URL, so not on a local server), plus three polling paths that need no public URL: a watcher that polls Campay for each new pending transaction (every 3 s for a minute, then every 10 s, up to 5 minutes), a refresh whenever a pending transaction is read (API, CLI, pay page), and `/internal/tick`. So a live deposit settles within seconds of the customer's approval even when running locally. If a transaction stays pending, look for a `sync failed` line in the server log.

Not yet confirmed against the real Campay: the webhook format (we assume query parameters including a `signature` JWT
signed with your webhook key), the phone format sent to Campay, and the balance endpoint path. If step 5 shows a mismatch,
the only file to fix is `app/providers/campay.py`.

## 8. Merchant webhooks

Register an endpoint (HTTPS required in live mode; private/local addresses are blocked):

```bash
curl -s $BASE/me/webhook-endpoints -H "Authorization: Bearer <JWT>" -H 'Content-Type: application/json' \
  -d '{"mode":"test","url":"https://example.com/hooks/paysawa","events":["collection.succeeded","payout.failed"]}'
# leave "events" empty for all events. Reveal the secret again anytime: GET /me/webhook-endpoints/{id}/secret
```

Events: `collection.succeeded`, `collection.failed`, `collection.expired`, `payout.succeeded`, `payout.failed`.
Body: `{"id":"evt_...","type":"...","created":"...","data":{<transaction object>}}`.
Headers: `X-Paysawa-Signature: t=<unix>,v1=<hex>`, `X-Paysawa-Event`, `X-Paysawa-Delivery`.
Reply with any 2xx. Failed deliveries are retried with exponential backoff (up to 8 attempts); see `GET /me/webhook-deliveries`.

Verify the signature (HMAC-SHA256 of `"<t>.<raw body>"` with your signing secret; reject if `t` is older than 5 minutes):

```python
import hmac, hashlib, time
def verify(secret: str, raw_body: bytes, header: str) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(","))
    if abs(time.time() - int(parts["t"])) > 300:
        return False
    expected = hmac.new(secret.encode(), f"{parts['t']}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])
```

```js
const crypto = require("crypto");
function verify(secret, rawBody, header) {
  const p = Object.fromEntries(header.split(",").map(s => s.split("=")));
  if (Math.abs(Date.now() / 1000 - Number(p.t)) > 300) return false;
  const expected = crypto.createHmac("sha256", secret).update(`${p.t}.${rawBody}`).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(p.v1));
}
```

## 9. Hosted pay page

The server serves a working pay page itself at `/pay/<session id>` (one static HTML file, `app/static/pay.html`): English or French automatically, mobile friendly, sandbox hints in test mode, live USSD help in live mode, 3 attempts, return button / auto redirect after payment, and a strict content-security policy (no framing, no external scripts). Create a session from the CLI (menu 6): it prints the link, opens it in your browser and watches until it is paid. Set `APP_BASE_URL` to your public URL so links are correct, and `PAY_GATE_URL` only if a separate frontend hosts the page later.

Session times are stored in UTC (`2026-10-17T20:50:08+00:00`); the API also returns `expires_in_seconds`, and the page and CLI show your local time. Links are valid for 60 minutes by default (`expires_in_minutes`, 1 to 1440).

### Contract for a separate frontend

Merchant creates a session (secret key auth):

```bash
curl -s $BASE/v1/checkout-sessions -H "Authorization: Bearer sk_test_..." -H 'Content-Type: application/json' \
  -d '{"amount":2000,"description":"Order 1001","merchant_reference":"1001","redirect_url":"https://shop.example.com/thanks"}'
# -> {"id":"cs_...","url":"<APP_BASE_URL>/pay/cs_...","status":"open","expires_in_seconds":3600,...}
```

The pay page uses these **public** endpoints (no auth, CORS enabled):

| Method | Path | Use |
|---|---|---|
| GET | `/gate/sessions/{id}` | merchant name, amount, description, `status` (`open`, `paid`, `expired`), `attempts_left` |
| POST | `/gate/sessions/{id}/pay` body `{"phone":"6XXXXXXXX"}` | start the payment; the customer approves on their phone |
| GET | `/gate/sessions/{id}/status` | poll every 2-3 s; `payment.status` is `pending`, `succeeded`, `failed` (with `failure_message`) |

When `status` becomes `paid`, the response contains `redirect_url`: send the customer there. The merchant also receives the
`collection.succeeded` webhook (its `data.checkout_session` and `data.merchant_reference` identify the order).
A session allows 3 attempts; public endpoints are rate limited per IP.

## 10. Deploy on Render (free plan) + Neon

* Build command: `pip install -r requirements.txt`
* Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
* Environment: every variable from `.env.example` (use the Neon pooled URL).
* Free web services sleep after 15 minutes idle, so use an external pinger (cron-job.org works) with two jobs:
  1. `GET <APP_BASE_URL>/health` every 10 minutes. It never touches the database, so Neon can still sleep.
  2. `GET <APP_BASE_URL>/internal/tick` every 5-10 minutes with header `X-Internal-Secret: <INTERNAL_TICK_SECRET>`.
     It delivers due webhooks, re-checks pending transactions with the provider (the safety net when a Campay
     webhook arrives while the service sleeps), expires stale items and records a ledger-vs-Campay balance comparison.
* For real money, plan to upgrade Render (no sleeping) and Neon (compute that does not hit free-plan hour limits).

## 11. Endpoint reference

| Auth | Endpoint | Purpose |
|---|---|---|
| none | `GET /health` | keep-alive (no DB) |
| none | `POST /auth/signup`, `POST /auth/login` | dashboard JWT |
| JWT | `GET /me`, `GET /me/balance`, `GET /me/transactions?mode=` | dashboard data |
| JWT | `POST/GET/DELETE /me/api-keys`, `GET /me/api-keys/{id}/secret` | key management and reveal |
| JWT | `POST/GET/DELETE /me/webhook-endpoints`, `GET /me/webhook-endpoints/{id}/secret`, `GET /me/webhook-deliveries` | webhooks |
| `sk_` key | `POST /v1/collections`, `GET /v1/collections/{id}` | collect |
| `sk_` key | `POST /v1/payouts`, `GET /v1/payouts/{id}` | pay out |
| `sk_` key | `GET /v1/balance`, `GET /v1/transactions` | balance, history |
| `sk_` key | `POST /v1/checkout-sessions`, `GET /v1/checkout-sessions/{id}` | hosted pay page |
| none | `GET /gate/sessions/{id}`, `POST /gate/sessions/{id}/pay`, `GET /gate/sessions/{id}/status` | pay page |
| provider | `GET/POST /webhooks/campay` | inbound Campay webhook |
| internal secret | `GET /internal/db-check`, `/internal/provider-check`, `/internal/tick` | operations |

Errors always look like `{"error": {"code": "insufficient_funds", "message": "..."}}`.

## 12. Known limits

* A payout whose provider call times out is left `pending` with its funds held, never auto-released (money may have moved). The tick reports the count under `payouts_needing_review`; resolve those by hand against the Campay dashboard.
* A collection whose provider call times out stays `pending` and is resolved by the Campay webhook (matched by our transaction id) or expires after 15 minutes.
* Rate limiting is in memory (single instance, resets on restart).
* Email verification, password reset, refunds and a KYC flow do not exist yet.
* Charging customers' phones through a public page can be abused: sessions cap attempts at 3 and endpoints are rate limited, but monitor `api_request_logs`/transactions once live.
* Collecting for third parties may need Campay's agreement and, depending on your activity, financial regulation in your country. This code does not settle that question.

## 13. Tests

`pytest` runs the unit tests (provider mapping, signatures, fees, phone formats, SSRF guard). The database-backed flows are covered by `python -m scripts.smoke_test` and `python -m scripts.smoke_test_extended` against a running server. Never set `ALLOW_PRIVATE_WEBHOOK_URLS=true` in production.

## 14. Apps: Campay-style credentials and the Campay-compatible API

Webhooks are only half of it. Like Campay, Paysawa gives each merchant **apps**: an **app username**, an **app password** and a **webhook key**
(all revealable any time with a show/hide toggle: CLI menu `a`, or `GET /me/apps/{id}/credentials`). An app uses the Campay-shaped API at
`<APP_BASE_URL>/api/`, so code written for Campay needs only a different base URL and different credentials:

| Call | Body / result |
|---|---|
| `POST /api/token/` | `{username, password}` -> `{token, expires_in}`; then send `Authorization: Token <token>` |
| `POST /api/collect/` | `{amount, currency, from, description, external_reference}` -> `{reference, ussd_code, operator, status}` |
| `POST /api/withdraw/` | `{amount, currency, to, description, external_reference}` -> `{reference, status, amount, currency, operator}` |
| `GET /api/transaction/{reference}/` | `{reference, status (PENDING / SUCCESSFUL / FAILED), amount, currency, operator, external_reference, ...}`; also accepts a payment-link reference (`cs_...`) |
| `GET /api/balance/` | `{total_balance, held_balance, currency}` (one balance per merchant, so `mtn_balance` / `orange_balance` are null) |
| `POST /api/get_payment_link/` | `{amount, currency, description, external_reference, redirect_url}` -> `{link, reference}` (the pay page) |

Errors are flat: `{"message": "...", "code": "..."}`. The app's mode (test/live) comes from the app, exactly as the API key's mode does elsewhere.

**Webhooks for apps are Campay-style:** a `GET` to the app's webhook URL with query parameters `status` (`SUCCESSFUL`, `FAILED`, `PENDING`),
`reference`, `amount`, `currency`, `operator`, `code`, `operator_reference`, `external_reference` and `signature`, where `signature` is a JWT (HS256) signed
with the app's webhook key over the same parameters. Verify it and compare the fields with what the signature covers
(see `merchant_app/paysawa_client.py::verify_webhook`). An app only receives events for transactions made through that app (including payments on its payment links).

**The demo merchant server** (`merchant_app/`, port 9000) is a complete example of a second server built on Paysawa: deposit, withdrawal, payment links,
its own transaction list kept in step by webhooks AND polling, and a webhook log. Setup is in `merchant_app/README.md`.

## 15. Documentation website, Markdown docs and the Python SDK

- **Markdown docs:** `docs/` in English and `docs/fr/` in French (start at `docs/README.md`): overview, getting started, authentication, test and live, webhooks, hosted pay page, errors,
  Python SDK, going live, FAQ, dashboard API, and one file per endpoint under `docs/api/`.
- **Website:** `docs_site/index.html` (open it in a browser, or it is served by the API at `/developers/`). It looks like Campay's docs: a sidebar, one page
  per endpoint with request examples in cURL / Python SDK / Python requests / JavaScript and response examples, search, an **EN/FR** switch (French by default for French browsers),
  a light and dark theme (code samples follow it), a layout for phones, tablets and desktops, and an **API base URL** box in the top bar that rewrites every example. It is plain HTML, CSS and JavaScript, so it can also be hosted on GitHub Pages, Netlify or any static host.
- **Edit and rebuild:** sources are `docs_src/pages/*.md` and `docs_src/pages_fr/*.md` (prose, English and French) and `docs_src/reference.py` with `docs_src/reference_fr.py` (endpoints; the build fails if a translation is missing). Put your real address in `docs_src/config.py` (`BASE_URL`),
  then run `python docs_src/build.py` to regenerate `docs/` and `docs_site/assets/content.js`.
- **Python SDK:** the `paysawa-python/` folder (a separate repository, published as `pip install paysawa`). `DEFAULT_BASE_URL` in `src/paysawa/client.py` and the
  GitHub user in `pyproject.toml` must be set before publishing. Its release guide is in the SDK's README and in the project hand-over notes.

