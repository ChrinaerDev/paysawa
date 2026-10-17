import json

import httpx
import jwt
import pytest

from app.providers.base import (
    CollectRequest,
    InvalidPhoneNumber,
    ProviderAuthError,
    ProviderError,
    ProviderRejected,
    ProviderStatus,
    ProviderUnavailable,
)
from app.providers.campay import CampayProvider, map_status, normalize_phone


def make_provider(handler, webhook_key="whk"):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return CampayProvider(
        base_url="https://demo.campay.net/api/",
        username="u",
        password="p",
        webhook_key=webhook_key,
        client=client,
    )


def collect_req():
    return CollectRequest(amount=100, phone="670000000", description="test", external_reference="ref-1")


def test_normalize_phone():
    assert normalize_phone("670000000") == "237670000000"
    assert normalize_phone("+237 670 000 000") == "237670000000"
    assert normalize_phone("237670000000") == "237670000000"
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone("12345")


def test_map_status():
    assert map_status("SUCCESSFUL") is ProviderStatus.SUCCEEDED
    assert map_status("FAILED") is ProviderStatus.FAILED
    assert map_status("PENDING") is ProviderStatus.PENDING
    assert map_status("something-new") is ProviderStatus.PENDING


async def test_collect_payload_and_token_cached():
    calls = {"token": 0}
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token/"):
            calls["token"] += 1
            return httpx.Response(200, json={"token": "T1", "expires_in": 180})
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"reference": "abc", "ussd_code": "*126#", "operator": "MTN"})

    provider = make_provider(handler)
    first = await provider.collect(collect_req())
    await provider.collect(collect_req())
    assert calls["token"] == 1
    assert seen["auth"] == "Token T1"
    assert seen["body"] == {
        "amount": "100",
        "currency": "XAF",
        "from": "237670000000",
        "description": "test",
        "external_reference": "ref-1",
    }
    assert first.reference == "abc"
    assert first.status is ProviderStatus.PENDING


async def test_401_triggers_one_token_refresh():
    state = {"tokens": 0, "calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token/"):
            state["tokens"] += 1
            return httpx.Response(200, json={"token": f"T{state['tokens']}"})
        state["calls"] += 1
        if request.headers["Authorization"] == "Token T1":
            return httpx.Response(401, json={"detail": "expired"})
        return httpx.Response(200, json={"total_balance": 5000, "mtn_balance": 3000, "orange_balance": 2000})

    provider = make_provider(handler)
    balance = await provider.get_balance()
    assert balance.total == 5000 and balance.mtn == 3000 and balance.orange == 2000
    assert state["tokens"] == 2 and state["calls"] == 2


async def test_error_mapping():
    mode = {"status": 500}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token/"):
            return httpx.Response(200, json={"token": "T"})
        if mode["status"] == 400:
            return httpx.Response(400, json={"message": "Invalid phone number"})
        return httpx.Response(mode["status"], json={})

    provider = make_provider(handler)
    with pytest.raises(ProviderUnavailable):
        await provider.collect(collect_req())
    mode["status"] = 400
    with pytest.raises(ProviderRejected) as exc:
        await provider.collect(collect_req())
    assert "Invalid phone number" in str(exc.value)


async def test_network_error_is_unavailable_not_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token/"):
            return httpx.Response(200, json={"token": "T"})
        raise httpx.ConnectTimeout("boom")

    provider = make_provider(handler)
    with pytest.raises(ProviderUnavailable):
        await provider.collect(collect_req())


async def test_bad_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "bad credentials"})

    provider = make_provider(handler)
    with pytest.raises(ProviderAuthError):
        await provider.get_balance()


async def test_get_transaction_maps_status():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token/"):
            return httpx.Response(200, json={"token": "T"})
        assert request.url.path.endswith("/transaction/abc/")
        return httpx.Response(
            200,
            json={"reference": "abc", "status": "SUCCESSFUL", "amount": "100", "external_reference": "ref-1", "operator": "MTN"},
        )

    provider = make_provider(handler)
    tx = await provider.get_transaction("abc")
    assert tx.status is ProviderStatus.SUCCEEDED
    assert tx.amount == 100 and tx.external_reference == "ref-1"


def test_verify_webhook():
    provider = make_provider(lambda r: httpx.Response(200), webhook_key="whk")
    good = jwt.encode({"x": 1}, "whk", algorithm="HS256")
    event = provider.verify_webhook({"signature": good, "reference": "abc", "status": "SUCCESSFUL", "external_reference": "ref-1"})
    assert event.status is ProviderStatus.SUCCEEDED and event.reference == "abc"
    assert "signature" not in event.raw
    with pytest.raises(ProviderError):
        provider.verify_webhook({"signature": jwt.encode({"x": 1}, "wrong", algorithm="HS256"), "reference": "abc"})
    with pytest.raises(ProviderError):
        provider.verify_webhook({"reference": "abc"})
