"""Async SQLAlchemy engine tuned for Neon's pooled (pgbouncer) endpoint."""
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def to_async_url(raw: str) -> URL:
    """Accept a plain Neon URL (postgres:// or postgresql://, with sslmode/channel_binding)
    and turn it into something SQLAlchemy+asyncpg understands."""
    url = make_url(raw).set(drivername="postgresql+asyncpg")
    query = {k: v for k, v in url.query.items() if k not in ("sslmode", "channel_binding")}
    query["prepared_statement_cache_size"] = "0"  # required behind pgbouncer (transaction mode)
    return url.set(query=query)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. The app reads a file named .env (not .env.example): "
                "run `cp .env.example .env`, put your Neon URL in .env, or set it as an environment variable."
            )
        _engine = create_async_engine(
            to_async_url(settings.database_url),
            pool_size=3,
            max_overflow=2,
            pool_pre_ping=True,   # Neon suspends idle computes; drop dead connections
            pool_recycle=300,
            pool_timeout=15,       # waiting for a free pooled connection
            connect_args={
                "ssl": True,
                "timeout": 20,          # connect timeout (Neon cold start can take a few seconds)
                "command_timeout": 30,  # never let one query hang a request forever
                "statement_cache_size": 0,
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
            },
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
