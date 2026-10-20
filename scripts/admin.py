"""Admin CLI for creating accounts without a frontend.

    python -m scripts.admin create-merchant --name "Ada Labs" --email ada@example.com --password 'S3cret-pass'
    python -m scripts.admin create-key --email ada@example.com --mode test --label dev
    python -m scripts.admin enable-live --email ada@example.com --per-txn 50000 --daily 200000
    python -m scripts.admin set-fees --email ada@example.com --collection-bps 250 --payout-bps 250
    python -m scripts.admin suspend --email ada@example.com        (or: activate)
    python -m scripts.admin credit-test --email ada@example.com --amount 100000   (test-mode balance only)
"""
import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.config import get_settings
from app.db import dispose_engine, get_sessionmaker
from app.errors import ApiError
from app.models import Merchant, Transaction
from app.services import ledger
from app.services import merchants as merchant_service


async def _merchant(session, email: str) -> Merchant:
    merchant = await merchant_service.get_by_email(session, email)
    if merchant is None:
        raise SystemExit(f"No merchant with email {email}")
    return merchant


async def run(args) -> None:
    async with get_sessionmaker()() as session:
        if args.command == "create-merchant":
            m = await merchant_service.create_merchant(session, name=args.name, email=args.email, password=args.password, live_enabled=args.live)
            print(f"Created merchant {m.id} ({m.email}), live_enabled={m.live_enabled}")
            if args.with_test_key:
                key, secret = await merchant_service.issue_api_key(session, m, "test", "default", get_settings().key_secret)
                print(f"Test API key: {secret}")
        elif args.command == "create-key":
            m = await _merchant(session, args.email)
            key, secret = await merchant_service.issue_api_key(session, m, args.mode, args.label, get_settings().key_secret)
            print(f"{args.mode} API key: {secret}")
        elif args.command == "enable-live":
            m = await _merchant(session, args.email)
            m.live_enabled = True
            if args.per_txn:
                m.per_txn_limit = args.per_txn
            if args.daily:
                m.daily_limit = args.daily
            await session.commit()
            print(f"Live enabled for {m.email}: per-transaction {m.per_txn_limit}, daily {m.daily_limit}")
        elif args.command == "set-fees":
            m = await _merchant(session, args.email)
            if args.collection_bps is not None:
                m.collection_fee_bps = args.collection_bps
            if args.payout_bps is not None:
                m.payout_fee_bps = args.payout_bps
            await session.commit()
            print(f"Fees for {m.email}: collection {m.collection_fee_bps} bps, payout {m.payout_fee_bps} bps")
        elif args.command in ("suspend", "activate"):
            m = await _merchant(session, args.email)
            m.status = "suspended" if args.command == "suspend" else "active"
            await session.commit()
            print(f"{m.email} is now {m.status}")
        elif args.command == "credit-test":
            # Gives a merchant sandbox money by posting a balanced journal against a synthetic collection.
            m = await _merchant(session, args.email)
            tx = Transaction(
                id=uuid.uuid4(), public_id=f"col_admin{uuid.uuid4().hex[:12]}", merchant_id=m.id, mode="test", type="collection",
                status="succeeded", amount=args.amount, fee=0, phone_number="237600000001", provider="simulated",
                description="Admin sandbox credit", meta={"user": {}},
            )
            session.add(tx)
            await session.flush()
            await ledger.post_collection_settled(session, tx)
            await session.commit()
            print(f"Credited {args.amount} XAF of TEST money to {m.email}")
    await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Paysawa admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-merchant")
    p.add_argument("--name", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--live", action="store_true", help="enable live mode immediately")
    p.add_argument("--with-test-key", action="store_true", help="also print a first test API key")

    p = sub.add_parser("create-key")
    p.add_argument("--email", required=True)
    p.add_argument("--mode", choices=["test", "live"], required=True)
    p.add_argument("--label", default=None)

    p = sub.add_parser("enable-live")
    p.add_argument("--email", required=True)
    p.add_argument("--per-txn", type=int, default=None)
    p.add_argument("--daily", type=int, default=None)

    p = sub.add_parser("set-fees")
    p.add_argument("--email", required=True)
    p.add_argument("--collection-bps", type=int, default=None)
    p.add_argument("--payout-bps", type=int, default=None)

    for name in ("suspend", "activate"):
        p = sub.add_parser(name)
        p.add_argument("--email", required=True)

    p = sub.add_parser("credit-test")
    p.add_argument("--email", required=True)
    p.add_argument("--amount", type=int, required=True)

    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except ApiError as exc:
        raise SystemExit(f"{exc.code}: {exc.message}")


if __name__ == "__main__":
    main()
