-- Migration 002 (run after schema.sql): hosted checkout sessions + automatic updated_at.

CREATE TABLE checkout_sessions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id          text NOT NULL UNIQUE,            -- 'cs_...' shown in URLs and the API
    merchant_id        uuid NOT NULL REFERENCES merchants(id),
    mode               text NOT NULL CHECK (mode IN ('test','live')),
    amount             bigint NOT NULL CHECK (amount > 0),
    currency           text NOT NULL DEFAULT 'XAF',
    description        text,
    merchant_reference text,
    redirect_url       text,                            -- where the pay page sends the customer after success
    status             text NOT NULL DEFAULT 'open' CHECK (status IN ('open','paid','expired')),
    attempts           integer NOT NULL DEFAULT 0,
    transaction_id     uuid REFERENCES transactions(id),  -- latest collection attempt
    metadata           jsonb NOT NULL DEFAULT '{}',
    expires_at         timestamptz NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    paid_at            timestamptz
);
CREATE INDEX checkout_sessions_merchant_idx ON checkout_sessions (merchant_id, created_at DESC);
CREATE INDEX checkout_sessions_open_idx ON checkout_sessions (expires_at) WHERE status = 'open';

-- transactions.updated_at was not maintained automatically in v1
CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER transactions_set_updated_at BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
