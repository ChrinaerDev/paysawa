# backend.md — Paysawa payment gateway (built on Campay)

> **Living document.** Maintained by the backend AI. Updated on every migration, schema change,
> endpoint change or architecture decision. Other AIs (frontend, webhook page, docs site) treat this
> as the source of truth and must not contradict it; propose changes instead.
>
> Legend: **[DONE]** implemented · **[VERIFY]** implemented on an assumption not yet confirmed against the real service · **[PLANNED]** not started.

Last updated: 2026-10-16 (third update)

---

## 1. Project in one paragraph

We hold live API access to **Campay** (mobile money gateway in Cameroon: MTN and Orange Money, XAF).
Paysawa is our own payment gateway on top of our single Campay app credentials. Merchants (tech-savvy
students, small online sellers) get API keys, a sandbox, webhooks, a hosted pay page and (later) a docs
site. Collections and payouts run through **our** Campay account; an internal double-entry ledger tracks
what each merchant owns. **Each merchant has ONE accumulated balance (no split by operator).** Deposits and
withdrawals work for any MTN or Orange number. Merchants never see Campay.

## 2. Status / changelog (newest first)

| Date | Change | Status |
|---|---|---|
| 2026-10-17 | **Campay-style apps + Campay-compatible API + demo merchant server.** New table `apps` and `webhook_endpoints.style/app_id` (`schema_003_apps.sql`, owner must apply). Apps = app username + app password + webhook key, revealable (derived from `API_KEY_SECRET`/`JWT_SECRET`, only sha256 of the password stored; webhook key never stored). Dashboard: `POST/GET/PATCH/DELETE /me/apps`, `GET /me/apps/{id}/credentials`. Campay-compatible API under `/api/`: `POST token/`, `collect/`, `withdraw/`, `get_payment_link/`, `GET transaction/{reference}/` (also `cs_` payment links), `balance/`; flat error shape `{message, code}`; `Authorization: Token <jwt>`. Campay-style webhooks to apps: `GET` with query params + `signature` JWT (HS256, app webhook key), only for that app's transactions (tx meta `app_id`, propagated through payment links). New `merchant_app/` (own FastAPI server on port 9000, own `PaysawaClient`, webhook + polling, HTML tester UI). CLI: menu `a` (apps). Verified offline: security/compat helpers, client and service against an imitation of the API (signatures cross-checked with the server's signer), CLI harness; NOT yet run end to end against the real server | DONE (pending owner's migration 003 + real test) |
| 2026-10-17 | **Hosted pay page built and served by the API itself** at `GET /pay/{session id}` (`app/static/pay.html`, `app/api/pages.py`): EN/FR, sandbox/live hints, 3 attempts, polling, return link + auto redirect (http/https only), merchant text rendered as plain text, CSP with per-request nonce, `frame-ancestors 'none'`. Session URLs now default to `{APP_BASE_URL}/pay/{id}` (`PAY_GATE_URL` optional override for a separate frontend). API additions: `expires_in_seconds` on session objects and the `/gate` view; minimum link validity lowered from 5 to 1 minute (to test expiry). Owner's report that a session 'expired at creation time' was a timezone coincidence (UTC timestamp, UTC+1 clock, 60 min default), not a bug; CLI and page now show local time. CLI: choose validity, opens the page, watches the session until paid. Page JS tested against a fake DOM (9 scenarios); not yet opened in a real browser by the owner | DONE |
| 2026-10-17 | **Bug fixed (first real LIVE deposit):** the customer approved, Campay credited the money, but our transaction stayed `pending` forever. Cause: with a local server Campay's webhook cannot reach us and nothing else asked Campay for the final status (the CLI only re-read our DB; `/internal/tick` was not scheduled). Per the official Campay SDK docs the final status is read with the status call (`PENDING|SUCCESSFUL|FAILED` via transaction reference). Fix: live/demo transactions now settle through FOUR paths: (1) inbound webhook, (2) on-demand refresh whenever a pending transaction is read (`GET /v1/collections/{id}`, `/v1/payouts/{id}`, `/v1/transactions`, `/me/transactions`, pay-page status), throttled to once per 3 s per transaction, (3) a per-transaction watcher started at creation (polls Campay every 3 s for 1 min then every 10 s, up to 5 min, only while pending), (4) `/internal/tick`. Existing stuck transactions settle the next time they are read or on a tick | DONE (not yet confirmed by owner with a second real deposit) |
| 2026-10-17 | Owner: extended smoke test ALL PASSED. **Keys are now revealable for test AND live** (owner decision: show/hide toggle, no show-once): secrets are derived `HMAC(API_KEY_SECRET or JWT_SECRET, mode+key id)`, DB still stores only sha256; new endpoints `GET /me/api-keys/{id}/secret` and `GET /me/webhook-endpoints/{id}/secret`; key list has `revealable`; keys created before this change return 409 `not_revealable`. Added `cli/` (menu-driven terminal client over the HTTP API: auth, deposit, withdraw, balances, keys with show/hide, webhooks + listener, checkout sessions, sandbox lab, checklist). CLI verified end to end against an in-memory fake of the API (not yet against the real server by the owner) | DONE |
| 2026-10-16 | Extended smoke test: webhook delivery + signature + payload PASSED; then `POST /v1/payouts` (to a failing number `...0000`, i.e. the failed-payout refund path, first time exercised) hung >45 s with a registered webhook endpoint present. Root cause UNKNOWN. Hardening added meanwhile: `SET LOCAL lock_timeout = 10s` before every `FOR UPDATE` (hang becomes a 503 `busy` plus a log line), 503 `db_timeout` for DB timeouts, request path in error logs. Waiting for uvicorn console output + `pg_stat_activity` snapshot; also suggested an A/B test with Neon's direct (non-pooler) URL | OPEN |
| 2026-10-16 | Owner's smoke test: ALL PASSED (login, key, collection, idempotency, fees, failed number, payout to Orange number, insufficient funds, checkout session, public pay endpoints) against real Neon in test mode. Added `scripts/smoke_test_extended.py` (webhook delivery + signature, failed payout refund, retry queue, tick) and dev-only setting `ALLOW_PRIVATE_WEBHOOK_URLS` (test mode only, default false) so webhooks can target localhost | DONE (extended script not yet run by owner) |
| 2026-10-16 | **Bug fixed** (found by owner's smoke test): `create_payout` read `available.balance` after `session.rollback()` (expired ORM object -> MissingGreenlet -> HTTP 500 instead of 402 `insufficient_funds`). Same hazard removed from the idempotency-race paths (`merchant.id` after rollback) in `create_collection`/`create_payout`. Smoke test no longer reuses keep-alive connections (a server 500 made the next request fail with ReadError) | DONE |
| 2026-10-16 | `scripts/smoke_test.py` rewritten: re-runnable (reuses fixed merchant `smoketest@paysawa.local`, relative balance checks, unique idempotency keys, revokes its key at the end, short errors, `--with-pending` optional). `db.py`: connect/command/pool timeouts so a stuck DB fails fast. `main.py`: unhandled errors return JSON `internal_error`. A user-reported timeout on `POST /me/api-keys` is NOT yet diagnosed (needs the uvicorn traceback) | DONE (timeout cause open) |
| 2026-10-16 | `config.py` now reads `.env` from the project root (not the launch folder); clearer error when `DATABASE_URL` is missing (user had filled `.env.example` instead of `.env`) | DONE |
| 2026-10-16 | Backend feature-complete for v1: auth + API keys, ledger service, collections, payouts, inbound Campay webhook, outgoing merchant webhooks, checkout sessions + public `/gate` API for the pay page, `/internal/tick`, simulated sandbox provider, admin CLI, smoke test, README | DONE (code written; unit tests pass; DB-backed flows NOT yet run against real Neon) |
| 2026-10-16 | `schema_002_checkout_sessions.sql` written: `checkout_sessions` table + `updated_at` trigger on `transactions` | DONE as file, **pending: owner must apply it in Neon** |
| 2026-10-16 | `schema.sql` v1 applied to Neon by the owner | DONE (platform seed now done by `python -m scripts.bootstrap`) |
| 2026-10-16 | Decision: no per-operator split of merchant balances or of `provider_float` | DECIDED |
| 2026-10-16 | Skeleton + `CampayProvider` + provider tests | DONE |

**Applied migrations:** `schema.sql` v1 (manual, Neon SQL editor). **Pending:** `schema_002_checkout_sessions.sql`. Not yet an Alembic baseline.
**Verified by tests (offline, stubbed HTTP):** provider mapping/token handling, password/JWT/API key/signature utilities, fees, phone formats, SSRF guard, simulated provider.
**Not yet run for real:** FastAPI app, SQLAlchemy against Neon, ledger triggers under the ORM, Campay live/demo calls. Owner runs `python -m scripts.bootstrap`, `/internal/db-check`, `python -m scripts.smoke_test`, then `/internal/provider-check?mode=live`.

## 3. Stack and hosting

| Concern | Choice |
|---|---|
| App | Python 3.11+, FastAPI (async), Pydantic v2, SQLAlchemy 2.0 + asyncpg |
| DB | PostgreSQL on Neon (pooled `-pooler` URL; app strips `sslmode`, enables TLS, disables prepared-statement cache) |
| API host | Render free web service (sleeps after 15 min idle) |
| Background work | no worker service: Postgres is the queue; `/internal/tick` called by an external pinger every 5-10 min; best-effort immediate webhook delivery via FastAPI BackgroundTasks after each request |
| Pinger | cron-job.org (or similar): `/health` every 10 min (never touches DB), `/internal/tick` every 5-10 min |
| Pay page | served by the API at `/pay/{id}` for development (a separate frontend can replace it via `PAY_GATE_URL`) |
| Docs site / dashboard frontends | [PLANNED] |

## 4. Architecture (modular monolith)

```
app/
  main.py            app, CORS, error handlers, /health, router wiring
  config.py          env settings
  db.py              async engine/session (Neon-safe)
  models.py          ORM mapping of the SQL schemas (never create_all)
  errors.py          ApiError -> {"error":{"code","message"}}
  security.py        scrypt passwords, dashboard JWT, API keys, ids, webhook signatures
  phone.py           normalize_phone (6XXXXXXXX | +2376XXXXXXXX | 2376XXXXXXXX -> 2376XXXXXXXX)
  fees.py            compute_fee (basis points, rounded up, < amount), MIN_AMOUNT = 10
  netsafety.py       SSRF guard for merchant URLs
  ratelimit.py       in-memory sliding-window limiter
  providers/         base.py (interface, errors), campay.py, simulated.py, registry.py (mode -> provider)
  services/          ledger, transactions, checkout, merchants, webhooks_out, serializers, jobs
  api/               deps, auth (dashboard/JWT), v1 (merchant/key), gate (public pay page), webhooks_in, internal
scripts/             bootstrap.py, admin.py, smoke_test.py, smoke_test_extended.py
cli/                 python -m cli (app.py screens, api.py HTTP client, state.py checklist, ui.py rich output); API-only client, reference for the frontend AI
tests/               test_campay_provider.py, test_core.py
```

Rule: Campay is only referenced under `providers/`. Public API, docs and webhook payloads never mention Campay (provider references are never serialized).

**Modes:** `live` keys use Campay production (real money). `test` keys use the built-in **simulated provider** (instant, deterministic, no external calls) unless `TEST_PROVIDER=campay_demo`. The key decides the mode; accounts, transactions, endpoints, sessions are all per mode.

## 5. Database

Authoritative DDL: `schema.sql` then `schema_002_checkout_sessions.sql`. Tables: `merchants`, `api_keys`, `webhook_endpoints`, `accounts`, `transactions`, `ledger_journals`, `ledger_entries`, `provider_events`, `webhook_deliveries` (also the job queue), `reconciliation_runs`, `api_request_logs` (declared; not written yet), `checkout_sessions`, `apps` (Campay-style credentials; `webhook_endpoints` also got `style` = `paysawa`|`campay` and `app_id`, migration `schema_003_apps.sql`).

DB-enforced invariants: balanced journals at commit; append-only ledger; merchant balances never negative; one journal per `(transaction, kind)`; idempotency key unique per `(merchant, mode)`; `updated_at` maintained by trigger (migration 002).

Platform ledger accounts (4 rows, `merchant_id IS NULL`): `platform_fees` and `provider_float` for `test` and `live`. Seeded by `python -m scripts.bootstrap`. Each merchant gets `merchant_available` and `merchant_held` per mode at signup.

ORM note: `Transaction.meta` / `CheckoutSession.meta` map the `metadata` column; merchant metadata lives in `meta["user"]`, internal markers (e.g. `checkout_session`, `provider_message`) beside it.

### Ledger (balance = credits - debits; all balances sum to 0)

| Event | Posting |
|---|---|
| Collection succeeded | DEBIT provider_float (amount) / CREDIT merchant_available (amount - fee) + CREDIT platform_fees (fee) |
| Payout requested | DEBIT merchant_available (amount + fee) / CREDIT merchant_held (amount + fee) |
| Payout succeeded | DEBIT merchant_held (amount + fee) / CREDIT provider_float (amount) + CREDIT platform_fees (fee) |
| Payout failed | DEBIT merchant_held (amount + fee) / CREDIT merchant_available (amount + fee) |

Live reconciliation: Campay total balance should equal `-provider_float(live)` plus any pre-existing balance (a constant offset is expected). `/internal/tick` records a `reconciliation_runs` row at most every 6 h.

### Transaction state machine
`created -> pending -> succeeded | failed | expired` (internal). The API shows `created` as `pending`. Transitions are idempotent and run under a row lock (`apply_provider_status`).

## 6. Provider error semantics (important)

- `ProviderRejected` (4xx): definite refusal; transaction fails, payout hold is released. Provider's message is stored internally, merchants see a generic message.
- `ProviderAuthError`: our credentials refused; same handling, generic "temporarily unavailable".
- `ProviderUnavailable` (timeout/5xx/429): **outcome unknown, never fail it.** Collection stays pending/created (resolved by Campay webhook via `external_reference` = our transaction id, or expires after 15 min). Payout stays `pending` with funds held and is surfaced as `payouts_needing_review` by the tick; resolved by hand.
- The transaction row is committed before every provider call.

## 7. Public API

Errors: `{"error": {"code", "message"}}`. Amounts are integer XAF. Phone accepts any MTN/Orange Cameroon number.

**Dashboard (JWT from `/auth/login` or `/auth/signup`):** `POST /auth/signup`, `POST /auth/login`, `GET /me`, `GET /me/balance` (both modes), `GET /me/transactions?mode&type&status&limit&offset`, `POST/GET /me/api-keys` (list items include `revealable`), `GET /me/api-keys/{id}/secret` (**reveal, test and live; the UI hides it behind a show/hide toggle**), `DELETE /me/api-keys/{id}`, `POST/GET /me/webhook-endpoints`, `GET /me/webhook-endpoints/{id}/secret`, `DELETE /me/webhook-endpoints/{id}`, `GET /me/webhook-deliveries`.

**Apps (JWT):** `POST /me/apps {name, mode, webhook_url?}`, `GET /me/apps`, `PATCH /me/apps/{id} {name?, webhook_url? ("" removes)}`, `GET /me/apps/{id}/credentials` -> `{username, password, webhook_key, api_base_url}` (UI: show/hide toggle), `DELETE /me/apps/{id}` (revoke).

**Campay-compatible API (`/api`, `Authorization: Token <token>` from `POST /api/token/`):** `token/`, `collect/`, `withdraw/`, `transaction/{reference}/`, `balance/` (`total_balance` = available, `held_balance`, per-operator fields null), `get_payment_link/`. References are Paysawa ids (`col_...`, `pay_...`, `cs_...`). Errors are flat `{message, code}`. Webhooks to apps: Campay-style signed GET (see README section 14).

**Merchant API (`Authorization: Bearer sk_test_...|sk_live_...`):** `POST /v1/collections`, `GET /v1/collections/{id}`, `POST /v1/payouts`, `GET /v1/payouts/{id}`, `GET /v1/balance`, `GET /v1/transactions`, `POST /v1/checkout-sessions`, `GET /v1/checkout-sessions/{id}`. POSTs accept `Idempotency-Key` (replay returns 200 with the original; different params return 409). Live requires `merchants.live_enabled` (admin CLI) and enforces per-transaction and daily limits (defaults 50 000 / 200 000 XAF).

**Transaction object:** `id` (`col_...`/`pay_...`), `object`, `mode`, `status` (`pending|succeeded|failed|expired`), `amount`, `fee`, `currency`, `phone_number`, `operator`, `description`, `merchant_reference`, `failure_code`, `failure_message`, `metadata`, `checkout_session`, `created_at`, `completed_at`.

**Pay-page contract (public, no auth, CORS enabled) — for the frontend AI:**
- `GET /gate/sessions/{id}`: `status` (`open|paid|expired`), `merchant_name`, `amount`, `currency`, `description`, `merchant_reference`, `expires_at`, `attempts_left`, `payment` (`status`, `failure_message`, `operator`) or null, `redirect_url` (only once paid).
- `POST /gate/sessions/{id}/pay` body `{"phone"}`: starts the collection; returns the same view. Errors: `already_paid`, `session_expired` (410), `too_many_attempts` (429, max 3), `payment_in_progress` (409), `invalid_phone`, `rate_limited`.
- `GET /gate/sessions/{id}/status`: poll every 2-3 s.
- Session URL is `{PAY_GATE_URL or APP_BASE_URL/pay}/{id}`; sessions expire after `expires_in_minutes` (default 60, 1 to 1440). Times are UTC; use `expires_in_seconds` for countdowns.

**Outgoing webhooks:** events `collection.succeeded|failed|expired`, `payout.succeeded|failed`. Body `{"id","type","created","data":<transaction object>}`. Headers `X-Paysawa-Signature: t=<unix>,v1=<hex HMAC-SHA256 of "t.rawbody" with the endpoint's signing secret>`, `X-Paysawa-Event`, `X-Paysawa-Delivery`. Any 2xx = delivered; exponential backoff (1 min doubling, cap 6 h), 8 attempts then `failed`. HTTPS required in live mode; private/local addresses blocked (also re-checked at delivery).

**Inbound Campay webhook:** `GET|POST /webhooks/campay` **[VERIFY format]**. Verifies signature, dedupes in `provider_events`, matches by `external_reference` (our transaction id) or provider reference, then re-fetches the status from Campay before settling (never trusts the webhook alone).

**Internal (header `X-Internal-Secret`):** `GET /internal/db-check`, `GET /internal/provider-check?mode=`, `GET|POST /internal/tick` (deliver due webhooks, reconcile pending with provider, expire stale collections/sessions, count payouts needing review, periodic balance reconciliation). `GET /health` never touches the DB.

## 8. Campay integration notes (`app/providers/campay.py`)

Taken from Campay's public SDKs; **[VERIFY]** against Campay's official docs / first real transactions:
- Base URLs: demo `https://demo.campay.net/api/`, production `https://campay.net/api/`.
- `POST token/`, `POST collect/` (amount string, currency, from, description, external_reference), `POST withdraw/` (to instead of from), `GET transaction/{reference}/`, `GET balance/` (SDKs disagree on the path). `Authorization: Token <token>`, cached, refreshed once on 401. API withdrawal must be enabled in Campay app settings.
- Phone sent as `2376XXXXXXXX`.
- Webhook assumed to arrive as query params with a `signature` JWT (HS256, webhook key).

### Settlement paths for live transactions (in order of speed)
1. Campay webhook to `/webhooks/campay` (needs a public URL; not available on a local server).
2. Per-transaction watcher (`services/jobs.py::watch_pending`) started right after creation.
3. On-demand refresh when a pending transaction is read (`services/transactions.py::refresh_if_pending`).
4. `/internal/tick` reconciliation (also covers server restarts, which lose watchers).
Every path ends in the same idempotent `apply_provider_status`, so double settlement is impossible. If a transaction stays pending, look for a `sync failed tx=...` warning in the server log: it carries the provider error.

## 9. Free-tier operating constraints

Render free service sleeps after 15 min idle; the external pinger keeps it warm and drives `/internal/tick`. `/health` must not touch the DB (Neon free compute sleeps after 5 min idle and has a monthly CU-hour quota). Polling in the tick is the safety net for webhooks that arrive while asleep. Neon free storage is 0.5 GB: prune `api_request_logs`/`provider_events` once they are used. For real money plan Render Starter and a paid Neon plan.

## 10. Environment variables (names only)

`DATABASE_URL`, `JWT_SECRET`, `INTERNAL_TICK_SECRET`, `APP_BASE_URL`, `PAY_GATE_URL` (empty = built-in page), `CORS_ORIGINS`, `ALLOW_SIGNUP`, `CAMPAY_LIVE_USERNAME`, `CAMPAY_LIVE_PASSWORD`, `CAMPAY_LIVE_WEBHOOK_KEY`, `CAMPAY_LIVE_BASE_URL`, `ALLOW_PRIVATE_WEBHOOK_URLS` (dev only), `API_KEY_SECRET` (optional, defaults to `JWT_SECRET`; never change once keys exist), `TEST_PROVIDER` (`simulated|campay_demo`), `CAMPAY_DEMO_USERNAME`, `CAMPAY_DEMO_PASSWORD`, `CAMPAY_DEMO_WEBHOOK_KEY`, `CAMPAY_DEMO_BASE_URL`.

## 11. Run, test, administer

See `README.md` (setup, programmatic account creation, going live, webhooks, pay-page contract, Render deploy). Scripts: `python -m scripts.bootstrap`, `python -m scripts.admin <create-merchant|create-key|enable-live|set-fees|suspend|activate|credit-test>`, `python -m scripts.smoke_test`. Tests: `pytest`.

## 12. Known gaps and open decisions

- OPEN BUG: failed-payout path hangs in the extended smoke test (see changelog). Not run against real Neon/Campay for live mode yet (see section 2). Owner reported a timeout on `POST /me/api-keys` during the smoke test after an earlier connection failure; root cause unknown, waiting for server log.
- Campay webhook format, phone format and balance path are assumptions (section 8).
- Two concurrent `/gate/.../pay` calls on one session can both start a collection (attempt cap of 3 bounds the damage).
- Campay's own fees on withdrawals are not modeled; payout fee (default 250 bps) must cover them: check Campay's schedule.
- `api_request_logs` table exists but nothing writes to it yet.
- In-memory rate limiter (single instance).
- Hot ledger rows (`platform_fees`, `provider_float`) serialize concurrent settlements; fine at small scale.
- Security trade-off (owner decision): live keys are revealable, so a stolen dashboard login exposes the live key. A cheap mitigation if wanted later: ask for the password again before revealing a live key.
- Not built: email verification, password reset, refunds, KYC flow, Alembic baseline, docs site.
- Regulatory and Campay-terms review for third-party collection is the owner's responsibility before onboarding real merchants.

## 13. Next steps

1. Owner applies `schema_002_checkout_sessions.sql`, runs bootstrap, `/internal/db-check`, smoke test; reports failures.
2. Owner tests live provider with tiny real amounts; fix `providers/campay.py` assumptions.
3. Deploy to Render, then a tiny real Campay test through the CLI's LIVE mode.
4. **Frontends (next phase):** (a) hosted pay page `/pay/{session id}` using the `/gate` contract above; (b) merchant dashboard (signup, keys, webhooks, transactions); (c) docs site from `/openapi.json` + README.
5. Docs: markdown documentation, then the documentation website (HTML/CSS/JS) for Paysawa after the owner has tested the app + demo merchant flow.
6. Later: Alembic baseline, request logging, refunds, email flows.

## 14. Rules for whoever edits this file

1. Add a changelog row for every migration, endpoint, schema or architecture change and update the status lines.
2. Move items to DONE only when actually applied or run.
3. Never put secrets here.
4. Backend rule learned the hard way: never read attributes of ORM objects after `session.rollback()` (it expires everything and an async session cannot lazy-load: MissingGreenlet). Copy needed values into local variables first.
5. Frontend/docs AIs: read sections 5 to 8; ask the backend AI before relying on anything marked VERIFY.
