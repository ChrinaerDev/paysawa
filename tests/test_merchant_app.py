"""Demo merchant app: client + service against an in-memory imitation of Paysawa's Campay-style API.
The webhook signatures come from the SERVER's own signer (app.security), so this also checks that both sides agree."""
import asyncio
import json
import uuid

import httpx
import pytest

from app import security
from app.services.compat import campay_params
from merchant_app.paysawa_client import PaysawaClient, PaysawaError
from merchant_app.service import MerchantService, Store

WEBHOOK_KEY = security.derive_app_webhook_key(uuid.uuid4(), "server-secret")


def make_state():
    return {"calls": [], "statuses": {}, "reject_redirect": False, "token_calls": 0, "expire_once": False}


def make_client(state):
    def handler(request):
        path = request.url.path
        body = json.loads(request.content) if request.content else {}
        state["calls"].append((path, body, dict(request.headers)))
        if path.endswith("/token/"):
            state["token_calls"] += 1
            if body.get("password") != "good":
                return httpx.Response(401, {"message": "Invalid app username or password.", "code": "invalid_credentials"})
            return httpx.Response(200, {"token": f"T{state['token_calls']}", "expires_in": 3600})
        if state["expire_once"] and request.headers.get("Authorization") == "Token T1":
            state["expire_once"] = False
            return httpx.Response(401, {"message": "Invalid or expired token.", "code": "unauthorized"})
        if path.endswith("/collect/"):
            return httpx.Response(200, {"reference": "col_1", "ussd_code": "*126#", "operator": "MTN", "status": "PENDING"})
        if path.endswith("/withdraw/"):
            return httpx.Response(200, {"reference": "pay_1", "status": "SUCCESSFUL", "amount": 1000, "currency": "XAF", "operator": "ORANGE"})
        if path.endswith("/balance/"):
            return httpx.Response(200, {"total_balance": 4875, "mtn_balance": None, "orange_balance": None, "held_balance": 0, "currency": "XAF"})
        if "/transaction/" in path:
            ref = path.split("/transaction/")[1].strip("/")
            return httpx.Response(200, state["statuses"].get(ref, {"reference": ref, "status": "PENDING"}))
        if path.endswith("/get_payment_link/"):
            if body.get("redirect_url") and state["reject_redirect"]:
                return httpx.Response(422, {"message": "https is required in live mode", "code": "invalid_redirect_url"})
            return httpx.Response(200, {"link": "http://localhost:8000/pay/cs_1", "reference": "cs_1"})
        return httpx.Response(404, {"message": "no such endpoint", "code": "not_found"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return PaysawaClient("http://localhost:8000/api/", "pa_test", "good", WEBHOOK_KEY, client=http)


class Tx:  # what the server would turn into webhook parameters
    def __init__(self, status="succeeded", amount=5000, ext="dep-1", ref="col_1"):
        self.status, self.public_id, self.amount, self.currency = status, ref, amount, "XAF"
        self.operator, self.provider_reference, self.merchant_reference = "MTN", "op-1", ext


def signed(tx):
    params = campay_params(tx)
    return {**params, "signature": security.sign_callback(WEBHOOK_KEY, params)}


# ------------------------------------------------------------------ client
async def test_token_is_cached_and_sent_campay_style():
    state = make_state()
    client = make_client(state)
    out = await client.collect(5000, "670000001", "Order", "order-1")
    await client.balance()
    assert out["reference"] == "col_1" and state["token_calls"] == 1
    path, body, headers = next(c for c in state["calls"] if c[0].endswith("/collect/"))
    assert headers["Authorization"] == "Token T1"
    assert body == {"amount": "5000", "currency": "XAF", "from": "670000001", "description": "Order", "external_reference": "order-1"}


async def test_expired_token_is_refreshed_once():
    state = make_state()
    client = make_client(state)
    await client.balance()
    state["expire_once"] = True
    assert (await client.balance())["total_balance"] == 4875
    assert state["token_calls"] == 2


async def test_errors_are_raised_with_code_and_message():
    state = make_state()
    bad = make_client(state)
    bad.password = "wrong"
    with pytest.raises(PaysawaError) as exc:
        await bad.balance()
    assert exc.value.code == "invalid_credentials" and exc.value.status == 401
    with pytest.raises(PaysawaError) as exc:
        await make_client(state).transaction.__self__._call("GET", "nope/")
    assert exc.value.code == "not_found"


def test_webhook_signature_from_the_servers_signer():
    client = make_client(make_state())
    params = signed(Tx())
    clean = client.verify_webhook(params)
    assert clean["status"] == "SUCCESSFUL" and clean["external_reference"] == "dep-1" and "signature" not in clean
    with pytest.raises(PaysawaError) as exc:                       # another value with a valid signature
        client.verify_webhook({**params, "amount": "1"})
    assert exc.value.code == "tampered"
    with pytest.raises(PaysawaError) as exc:
        client.verify_webhook({**params, "signature": security.sign_callback("whk_wrong", campay_params(Tx()))})
    assert exc.value.code == "invalid_signature"
    with pytest.raises(PaysawaError) as exc:
        client.verify_webhook({k: v for k, v in params.items() if k != "signature"})
    assert exc.value.code == "missing_signature"


# ------------------------------------------------------------------ service
async def test_deposit_then_webhook_marks_it_successful():
    state = make_state()
    svc = MerchantService(make_client(state), Store(None), "http://localhost:9000")
    rec = await svc.deposit(5000, "670000001", "Order")
    assert rec["status"] == "PENDING" and rec["reference"] == "col_1" and rec["ussd_code"] == "*126#"
    await svc.handle_webhook(signed(Tx(ext=rec["external_reference"])))
    assert svc.store.records[rec["id"]]["status"] == "SUCCESSFUL"
    assert svc.webhook_log[0]["valid"] and "is now SUCCESSFUL" in svc.webhook_log[0]["summary"]


async def test_webhook_with_wrong_amount_or_unknown_reference_changes_nothing():
    svc = MerchantService(make_client(make_state()), Store(None), "")
    rec = await svc.deposit(5000, "670000001")
    await svc.handle_webhook(signed(Tx(amount=10, ext=rec["external_reference"])))
    assert svc.store.records[rec["id"]]["status"] == "PENDING" and "IGNORED" in svc.webhook_log[0]["summary"]
    await svc.handle_webhook(signed(Tx(ext="someone-elses")))
    assert svc.store.records[rec["id"]]["status"] == "PENDING" and "no local record" in svc.webhook_log[0]["summary"]
    with pytest.raises(PaysawaError):
        await svc.handle_webhook({**signed(Tx(ext=rec["external_reference"])), "signature": "garbage"})
    assert svc.webhook_log[0]["valid"] is False and svc.store.records[rec["id"]]["status"] == "PENDING"


async def test_polling_settles_a_record_without_any_webhook():
    state = make_state()
    svc = MerchantService(make_client(state), Store(None), "")
    rec = await svc.deposit(5000, "670000001")
    state["statuses"]["col_1"] = {"reference": "col_1", "status": "SUCCESSFUL", "operator": "MTN"}
    await svc.refresh_pending()
    assert svc.store.records[rec["id"]]["status"] == "SUCCESSFUL"


async def test_withdrawal_result_is_taken_from_the_response():
    svc = MerchantService(make_client(make_state()), Store(None), "")
    rec = await svc.withdraw(1000, "690000001", "Refund")
    assert rec["status"] == "SUCCESSFUL" and rec["operator"] == "ORANGE" and rec["kind"] == "withdrawal"


async def test_payment_link_without_redirect_when_live_refuses_it_and_failed_attempt_keeps_link_open():
    state = make_state()
    state["reject_redirect"] = True
    svc = MerchantService(make_client(state), Store(None), "http://localhost:9000")
    rec = await svc.payment_link(2000, "Order")
    assert rec["link"].endswith("/pay/cs_1") and "No redirect" in rec["note"] and rec["status"] == "PENDING"
    sent = [b for p, b, h in state["calls"] if p.endswith("/get_payment_link/")]
    assert sent[0].get("redirect_url") == "http://localhost:9000/thanks" and "redirect_url" not in sent[1]
    await svc.handle_webhook(signed(Tx(status="failed", amount=2000, ext=rec["external_reference"], ref="col_9")))
    assert svc.store.records[rec["id"]]["status"] == "PENDING"                      # customer may retry on the same link
    await svc.handle_webhook(signed(Tx(status="succeeded", amount=2000, ext=rec["external_reference"], ref="col_10")))
    assert svc.store.records[rec["id"]]["status"] == "SUCCESSFUL"
