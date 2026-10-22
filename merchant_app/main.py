"""Demo merchant server. Runs on its own port and talks to Paysawa ONLY through the apps API,
with an app's username / password / webhook key."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from merchant_app.config import get_settings
from merchant_app.paysawa_client import PaysawaClient, PaysawaError
from merchant_app.service import MerchantService, Store

HERE = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    client = PaysawaClient(base_url=s.paysawa_base_url, username=s.paysawa_username, password=s.paysawa_password, webhook_key=s.paysawa_webhook_key)
    app.state.client = client
    app.state.service = MerchantService(client, Store(HERE / "data.json"), s.public_url)
    yield
    await client.aclose()


app = FastAPI(title="Paysawa demo merchant app", version="0.1.0", lifespan=lifespan)


@app.exception_handler(PaysawaError)
async def paysawa_error(_: Request, exc: PaysawaError):
    status = exc.status if 400 <= exc.status < 600 else 502
    return JSONResponse(status_code=status, content={"error": {"code": exc.code, "message": exc.message}})


def service(request: Request) -> MerchantService:
    if not get_settings().paysawa_username:
        raise PaysawaError(503, "not_configured", "Fill merchant_app/.env with the app username, password and webhook key from Paysawa, then restart.")
    return request.app.state.service


class DepositIn(BaseModel):
    amount: int = Field(gt=0)
    phone: str = Field(min_length=9, max_length=20)
    description: str = Field(default="", max_length=120)


class LinkIn(BaseModel):
    amount: int = Field(gt=0)
    description: str = Field(default="", max_length=120)
    redirect: bool = True


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return (HERE / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/thanks", response_class=HTMLResponse)
async def thanks() -> str:
    return ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<body style='font-family:system-ui;max-width:420px;margin:20vh auto;text-align:center'>"
            "<h1>Thank you!</h1><p>Your payment was received. (This page belongs to the demo merchant app.)</p>"
            "<p><a href='/'>Back to the merchant dashboard</a></p></body>")


@app.get("/api/status")
async def status(request: Request):
    s = get_settings()
    out = {"configured": bool(s.paysawa_username and s.paysawa_password), "paysawa_base_url": s.paysawa_base_url,
           "username": s.paysawa_username, "webhook_url": f"{s.public_url.rstrip('/')}/webhooks/paysawa", "has_webhook_key": bool(s.paysawa_webhook_key)}
    if out["configured"]:
        try:
            out["balance"] = await request.app.state.client.balance()
        except PaysawaError as exc:
            out["error"] = f"{exc.code}: {exc.message}"
    return out


@app.get("/api/balance")
async def balance(request: Request):
    service(request)
    return await request.app.state.client.balance()


@app.post("/api/deposit")
async def deposit(body: DepositIn, request: Request):
    return await service(request).deposit(body.amount, body.phone, body.description)


@app.post("/api/withdraw")
async def withdraw(body: DepositIn, request: Request):
    return await service(request).withdraw(body.amount, body.phone, body.description)


@app.post("/api/payment-link")
async def payment_link(body: LinkIn, request: Request):
    return await service(request).payment_link(body.amount, body.description, body.redirect)


@app.get("/api/transactions")
async def transactions(request: Request):
    svc = service(request)
    await svc.refresh_pending()
    return {"data": svc.store.all()}


@app.get("/api/webhook-log")
async def webhook_log(request: Request):
    return {"data": list(service(request).webhook_log)}


@app.api_route("/webhooks/paysawa", methods=["GET", "POST"])
async def paysawa_webhook(request: Request):
    """Paysawa calls this: a GET with query parameters and a signed `signature`."""
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                params.update({k: str(v) for k, v in body.items()})
        except ValueError:
            pass
    return await service(request).handle_webhook(params)
