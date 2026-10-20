"""Idempotent first-run check: verifies the schema and seeds the 4 platform ledger accounts.

    python -m scripts.bootstrap
"""
import asyncio

from sqlalchemy import text

from app.db import dispose_engine, get_sessionmaker

SEED = """
INSERT INTO accounts (merchant_id, mode, type)
SELECT NULL, v.mode, v.type
FROM (VALUES ('test','platform_fees'), ('test','provider_float'),
             ('live','platform_fees'), ('live','provider_float')) AS v(mode, type)
WHERE NOT EXISTS (
    SELECT 1 FROM accounts a WHERE a.merchant_id IS NULL AND a.mode = v.mode AND a.type = v.type
)
"""


async def main() -> None:
    async with get_sessionmaker()() as session:
        await session.execute(text("SELECT 1"))
        tables = {
            row[0]
            for row in (await session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))).all()
        }
        needed = {"merchants", "api_keys", "accounts", "transactions", "ledger_entries", "webhook_deliveries"}
        missing = needed - tables
        if missing:
            raise SystemExit(f"Schema is missing tables {sorted(missing)}. Run schema.sql in Neon first.")
        if "checkout_sessions" not in tables:
            raise SystemExit("Run schema_002_checkout_sessions.sql in Neon first.")
        if "apps" not in tables:
            raise SystemExit("Run schema_003_apps.sql in Neon first.")
        result = await session.execute(text(SEED))
        await session.commit()
        print(f"Platform accounts: {result.rowcount} created (4 total expected).")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
