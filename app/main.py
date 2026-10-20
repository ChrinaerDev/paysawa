import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import apps, auth, compat, gate, internal, pages, v1, webhooks_in
from app.config import get_settings
from app.db import dispose_engine
from app.errors import ApiError
from app.providers.registry import ProviderRegistry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.registry = ProviderRegistry(settings)
    # used for outgoing merchant webhooks; never follow redirects (SSRF hygiene)
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(8.0), follow_redirects=False)
    yield
    await app.state.http.aclose()
    await app.state.registry.aclose()
    await dispose_engine()


app = FastAPI(title="Paysawa Payment Gateway", version="0.2.0", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_request", "message": f"{where}: {first.get('msg', 'invalid value')}".strip(": ")}},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log = logging.getLogger("paysawa")
    text_ = str(exc).lower()
    if "lock timeout" in text_:
        log.error("LOCK TIMEOUT on %s %s: another transaction holds a row this request needs. %s", request.method, request.url.path, str(exc)[:500])
        return JSONResponse(status_code=503, content={"error": {"code": "busy", "message": "Another operation on this account is in progress. Retry in a few seconds."}})
    if "timeout" in text_ or isinstance(exc, TimeoutError):
        log.error("DB TIMEOUT on %s %s: %s %s", request.method, request.url.path, type(exc).__name__, str(exc)[:500])
        return JSONResponse(status_code=503, content={"error": {"code": "db_timeout", "message": "The database did not answer in time. Retry shortly."}})
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": f"{type(exc).__name__}: see server logs"}})


@app.get("/health")
async def health() -> dict:
    """Keep-alive target for the external pinger. Must NEVER touch the database
    (Neon free compute would never suspend and would burn its monthly CU-hours)."""
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(v1.router)
app.include_router(apps.router)
app.include_router(compat.router)
app.include_router(gate.router)
app.include_router(pages.router)
app.include_router(webhooks_in.router)
app.include_router(internal.router)
