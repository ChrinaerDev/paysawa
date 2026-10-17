-- Campay wrapper gateway: PostgreSQL schema (Neon)
-- Money: integer minor units stored as BIGINT (XAF has no decimals, so 1 XAF = 1).
-- Ledger convention: balance = credits - debits, for every account.
-- Sum of all account balances is always 0. provider_float goes negative as
-- money arrives from Campay, so: Campay balance == -(provider_float balance).

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- ---------------------------------------------------------------- merchants
CREATE TABLE merchants (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name              text NOT NULL,
    email             text NOT NULL UNIQUE,
    password_hash     text NOT NULL,
    status            text NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active','suspended','closed')),
    live_enabled      boolean NOT NULL DEFAULT false,      -- real money allowed?
    kyc_level         smallint NOT NULL DEFAULT 0,         -- 0 = unverified
    per_txn_limit     bigint NOT NULL DEFAULT 50000  CHECK (per_txn_limit > 0),
    daily_limit       bigint NOT NULL DEFAULT 200000 CHECK (daily_limit > 0),
    collection_fee_bps integer NOT NULL DEFAULT 250 CHECK (collection_fee_bps >= 0), -- 250 = 2.50%
    payout_fee_bps     integer NOT NULL DEFAULT 250 CHECK (payout_fee_bps >= 0),
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE api_keys (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id   uuid NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    mode          text NOT NULL CHECK (mode IN ('test','live')),
    label         text,
    prefix        text NOT NULL UNIQUE,   -- e.g. 'sk_live_ab12cd34' (shown in dashboard)
    key_hash      text NOT NULL,          -- sha256 of full secret; never store the secret
    last_used_at  timestamptz,
    revoked_at    timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX api_keys_merchant_idx ON api_keys (merchant_id);

CREATE TABLE webhook_endpoints (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id   uuid NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    mode          text NOT NULL CHECK (mode IN ('test','live')),
    url           text NOT NULL,
    signing_secret text NOT NULL,         -- HMAC secret for outgoing signatures
    events        text[] NOT NULL DEFAULT '{}',   -- empty = all events
    is_active     boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX webhook_endpoints_merchant_idx ON webhook_endpoints (merchant_id, mode);

-- ------------------------------------------------------------------- ledger
CREATE TABLE accounts (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id  uuid REFERENCES merchants(id),   -- NULL for platform accounts
    mode         text NOT NULL CHECK (mode IN ('test','live')),
    type         text NOT NULL CHECK (type IN
                 ('merchant_available','merchant_held','platform_fees','provider_float')),
    currency     text NOT NULL DEFAULT 'XAF',
    balance      bigint NOT NULL DEFAULT 0,       -- maintained by trigger below
    created_at   timestamptz NOT NULL DEFAULT now(),
    -- merchants can never go negative (prevents overdraft / double spend)
    CONSTRAINT merchant_no_overdraft CHECK (type NOT LIKE 'merchant\_%' OR balance >= 0),
    CONSTRAINT merchant_acct_has_owner CHECK ((type LIKE 'merchant\_%') = (merchant_id IS NOT NULL))
);
CREATE UNIQUE INDEX accounts_unique_idx
    ON accounts (COALESCE(merchant_id, '00000000-0000-0000-0000-000000000000'::uuid), mode, type, currency);

-- ------------------------------------------------------------- transactions
CREATE TABLE transactions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id           text NOT NULL UNIQUE,     -- 'col_...' / 'pay_...' shown in the API
    merchant_id         uuid NOT NULL REFERENCES merchants(id),
    mode                text NOT NULL CHECK (mode IN ('test','live')),
    type                text NOT NULL CHECK (type IN ('collection','payout')),
    status              text NOT NULL DEFAULT 'created'
                        CHECK (status IN ('created','pending','succeeded','failed','expired')),
    amount              bigint NOT NULL CHECK (amount > 0),
    fee                 bigint NOT NULL DEFAULT 0 CHECK (fee >= 0),
    currency            text NOT NULL DEFAULT 'XAF',
    phone_number        text NOT NULL,
    operator            text,                     -- 'MTN' | 'ORANGE' (from provider)
    description         text,
    merchant_reference  text,                     -- merchant's own order id
    idempotency_key     text,
    provider            text NOT NULL DEFAULT 'campay',
    provider_reference  text,                     -- Campay's transaction reference
    provider_status     text,
    failure_code        text,
    failure_message     text,
    metadata            jsonb NOT NULL DEFAULT '{}',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    completed_at        timestamptz
);
-- the transaction's id is also what we send to Campay as external_reference
CREATE UNIQUE INDEX transactions_idem_idx
    ON transactions (merchant_id, mode, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX transactions_provider_ref_idx
    ON transactions (provider, provider_reference) WHERE provider_reference IS NOT NULL;
CREATE INDEX transactions_merchant_created_idx ON transactions (merchant_id, created_at DESC);
CREATE INDEX transactions_pending_idx ON transactions (updated_at) WHERE status = 'pending';

CREATE TABLE ledger_journals (
    id              bigserial PRIMARY KEY,
    transaction_id  uuid NOT NULL REFERENCES transactions(id),
    kind            text NOT NULL CHECK (kind IN
                    ('collection_settled','payout_hold','payout_settled','payout_released')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (transaction_id, kind)       -- each step can only be posted once (idempotent)
);

CREATE TABLE ledger_entries (
    id          bigserial PRIMARY KEY,
    journal_id  bigint NOT NULL REFERENCES ledger_journals(id),
    account_id  uuid NOT NULL REFERENCES accounts(id),
    direction   text NOT NULL CHECK (direction IN ('debit','credit')),
    amount      bigint NOT NULL CHECK (amount > 0),
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ledger_entries_account_idx ON ledger_entries (account_id, created_at DESC);
CREATE INDEX ledger_entries_journal_idx ON ledger_entries (journal_id);

-- keep accounts.balance in sync; the row lock serializes concurrent payouts
CREATE FUNCTION apply_entry_to_balance() RETURNS trigger AS $$
BEGIN
    UPDATE accounts
       SET balance = balance + CASE NEW.direction WHEN 'credit' THEN NEW.amount ELSE -NEW.amount END
     WHERE id = NEW.account_id;
    RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER ledger_entries_balance AFTER INSERT ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION apply_entry_to_balance();

-- every journal must balance (debits = credits), checked at COMMIT
CREATE FUNCTION assert_journal_balanced() RETURNS trigger AS $$
DECLARE diff bigint;
BEGIN
    SELECT COALESCE(SUM(CASE direction WHEN 'debit' THEN amount ELSE -amount END), 0)
      INTO diff FROM ledger_entries WHERE journal_id = NEW.journal_id;
    IF diff <> 0 THEN
        RAISE EXCEPTION 'journal % is unbalanced by %', NEW.journal_id, diff;
    END IF;
    RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER ledger_entries_balanced AFTER INSERT ON ledger_entries
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION assert_journal_balanced();

-- ledger is append-only
CREATE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION '% on % is not allowed (append-only)', TG_OP, TG_TABLE_NAME; END $$ LANGUAGE plpgsql;
CREATE TRIGGER ledger_entries_immutable BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER ledger_journals_immutable BEFORE UPDATE OR DELETE ON ledger_journals
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- Posting patterns (done in app code, inside one DB transaction):
--   collection succeeded: DEBIT provider_float (amount) / CREDIT merchant_available (amount-fee) + CREDIT platform_fees (fee)
--   payout requested:     DEBIT merchant_available (amount+fee) / CREDIT merchant_held (amount+fee)
--   payout succeeded:     DEBIT merchant_held (amount+fee) / CREDIT provider_float (amount) + CREDIT platform_fees (fee)
--   payout failed:        DEBIT merchant_held (amount+fee) / CREDIT merchant_available (amount+fee)

-- --------------------------------------------------- webhooks (in and out)
CREATE TABLE provider_events (               -- raw inbound webhooks from Campay
    id            bigserial PRIMARY KEY,
    provider      text NOT NULL DEFAULT 'campay',
    dedupe_key    text NOT NULL,             -- e.g. reference + status
    payload       jsonb NOT NULL,
    signature_valid boolean NOT NULL,
    processed_at  timestamptz,
    error         text,
    received_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, dedupe_key)
);

-- doubles as the job queue: worker does
--   SELECT ... WHERE status='pending' AND next_attempt_at <= now()
--   FOR UPDATE SKIP LOCKED LIMIT n
CREATE TABLE webhook_deliveries (
    id              bigserial PRIMARY KEY,
    endpoint_id     uuid NOT NULL REFERENCES webhook_endpoints(id) ON DELETE CASCADE,
    transaction_id  uuid REFERENCES transactions(id),
    event_type      text NOT NULL,           -- 'collection.succeeded', 'payout.failed', ...
    payload         jsonb NOT NULL,
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','delivered','failed')),
    attempts        integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_status_code integer,
    last_error      text,
    delivered_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX webhook_deliveries_due_idx ON webhook_deliveries (next_attempt_at) WHERE status = 'pending';

-- ------------------------------------------------------------ ops / safety
CREATE TABLE reconciliation_runs (
    id                bigserial PRIMARY KEY,
    ran_at            timestamptz NOT NULL DEFAULT now(),
    ledger_total      bigint NOT NULL,       -- -(provider_float balance), live mode
    provider_balance  bigint NOT NULL,       -- from Campay balance endpoint
    diff              bigint GENERATED ALWAYS AS (provider_balance - ledger_total) STORED,
    note              text
);

-- Keep small: Neon free = 0.5 GB. Prune with a scheduled DELETE (e.g. keep 30 days).
CREATE TABLE api_request_logs (
    id           bigserial PRIMARY KEY,
    merchant_id  uuid REFERENCES merchants(id) ON DELETE SET NULL,
    api_key_id   uuid REFERENCES api_keys(id) ON DELETE SET NULL,
    method       text NOT NULL,
    path         text NOT NULL,
    status_code  integer NOT NULL,
    ip           inet,
    duration_ms  integer,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX api_request_logs_created_idx ON api_request_logs (created_at);
CREATE INDEX api_request_logs_merchant_idx ON api_request_logs (merchant_id, created_at DESC);
