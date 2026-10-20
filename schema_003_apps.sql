-- Migration 003 (run after schema_002): Campay-style "apps" (username / password / webhook key) and
-- Campay-style webhook endpoints (GET with a signed `signature`) attached to an app.

CREATE TABLE apps (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id    uuid NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    mode           text NOT NULL CHECK (mode IN ('test','live')),
    name           text NOT NULL,
    username       text NOT NULL UNIQUE,          -- public app id, e.g. pa_1a2b3c4d5e6f7a8b
    password_hash  text NOT NULL,                 -- sha256 of the app password (the password itself is re-derivable, never stored)
    webhook_url    text,
    revoked_at     timestamptz,
    last_used_at   timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX apps_merchant_idx ON apps (merchant_id, created_at DESC);

ALTER TABLE webhook_endpoints
    ADD COLUMN style  text NOT NULL DEFAULT 'paysawa' CHECK (style IN ('paysawa','campay')),
    ADD COLUMN app_id uuid REFERENCES apps(id) ON DELETE CASCADE;
CREATE UNIQUE INDEX webhook_endpoints_app_idx ON webhook_endpoints (app_id) WHERE app_id IS NOT NULL;
