import jwt
import pytest

from app import security
from app.fees import MIN_AMOUNT, compute_fee
from app.netsafety import UnsafeUrl, check_public_url
from app.phone import normalize_phone
from app.providers.base import CollectRequest, PayoutRequest, ProviderStatus
from app.providers.simulated import SimulatedProvider


def test_password_roundtrip():
    stored = security.hash_password("correct horse")
    assert stored.startswith("scrypt$")
    assert security.verify_password("correct horse", stored)
    assert not security.verify_password("wrong", stored)
    assert not security.verify_password("x", "garbage")


def test_jwt_roundtrip_and_tamper():
    import uuid

    mid = uuid.uuid4()
    token = security.create_access_token(mid, "secret")
    assert security.decode_access_token(token, "secret") == mid
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(token, "other-secret")
    api_like = jwt.encode({"sub": str(mid), "typ": "other"}, "secret", algorithm="HS256")
    with pytest.raises(ValueError):
        security.decode_access_token(api_like, "secret")


def test_api_keys():
    full, prefix, digest = security.generate_api_key("test")
    assert full.startswith("sk_test_") and prefix == full[:16] and len(prefix) == security.KEY_PREFIX_LEN
    assert security.hash_api_key(full) == digest
    assert security.generate_api_key("live")[0].startswith("sk_live_")
    with pytest.raises(ValueError):
        security.generate_api_key("prod")


def test_webhook_signature():
    body = b'{"type":"collection.succeeded"}'
    header = security.sign_payload("whsec_x", body, 1_700_000_000)
    assert security.verify_signature("whsec_x", body, header, now=1_700_000_100)
    assert not security.verify_signature("whsec_y", body, header, now=1_700_000_100)
    assert not security.verify_signature("whsec_x", body + b" ", header, now=1_700_000_100)
    assert not security.verify_signature("whsec_x", body, header, now=1_700_001_000)  # too old
    assert not security.verify_signature("whsec_x", body, "nonsense", now=1_700_000_100)


def test_fees():
    assert compute_fee(5000, 250) == 125
    assert compute_fee(10, 250) == 1          # rounds up
    assert compute_fee(100, 0) == 0
    assert compute_fee(2, 10_000) == 1        # never swallows the whole amount
    assert MIN_AMOUNT >= 1


def test_phone_formats_for_both_operators():
    assert normalize_phone("670000001") == "237670000001"   # MTN style
    assert normalize_phone("690000001") == "237690000001"   # Orange style
    assert normalize_phone("+237 655 00 00 02") == "237655000002"


def test_ssrf_guard():
    for bad in ("https://127.0.0.1/hook", "https://10.0.0.5/x", "https://169.254.169.254/latest", "ftp://example.com", "https://user:pw@8.8.8.8/x"):
        with pytest.raises(UnsafeUrl):
            check_public_url(bad)
    with pytest.raises(UnsafeUrl):
        check_public_url("http://8.8.8.8/x")  # http not allowed in live mode
    check_public_url("http://8.8.8.8/x", allow_http=True)
    check_public_url("https://8.8.8.8/x")
    check_public_url("http://127.0.0.1:9000/hook", allow_http=True, allow_private=True)  # dev switch
    with pytest.raises(UnsafeUrl):
        check_public_url("http://127.0.0.1:9000/hook", allow_http=True)  # still blocked by default


async def test_simulated_provider_outcomes():
    sim = SimulatedProvider()
    ok = await sim.collect(CollectRequest(amount=100, phone="670000001", description="d", external_reference="r"))
    assert (await sim.get_transaction(ok.reference)).status is ProviderStatus.SUCCEEDED
    bad = await sim.collect(CollectRequest(amount=100, phone="670000000", description="d", external_reference="r"))
    assert (await sim.get_transaction(bad.reference)).status is ProviderStatus.FAILED
    pend = await sim.payout(PayoutRequest(amount=100, phone="690009999", description="d", external_reference="r"))
    assert (await sim.get_transaction(pend.reference)).status is ProviderStatus.PENDING
    assert sim.settles_immediately


def test_revealable_keys_are_deterministic_and_bound_to_secret():
    import uuid

    kid = uuid.uuid4()
    full, prefix, digest = security.make_api_key("live", kid, "server-secret")
    assert full == security.derive_api_key("live", kid, "server-secret")      # same inputs, same key: can be shown again
    assert full.startswith("sk_live_") and prefix == full[:security.KEY_PREFIX_LEN]
    assert security.hash_api_key(full) == digest
    assert security.derive_api_key("live", kid, "other-secret") != full          # tied to the server secret
    assert security.derive_api_key("live", uuid.uuid4(), "server-secret") != full  # tied to the key id
    assert security.derive_api_key("test", kid, "server-secret") != full         # tied to the mode


def test_app_credentials_tokens_and_callback_signature():
    import uuid

    app_id = uuid.uuid4()
    password = security.derive_app_password(app_id, "server-secret")
    assert password == security.derive_app_password(app_id, "server-secret")           # revealable: same every time
    assert password != security.derive_app_password(app_id, "other-secret")
    assert password != security.derive_app_password(uuid.uuid4(), "server-secret")
    key = security.derive_app_webhook_key(app_id, "server-secret")
    assert key.startswith("whk_") and key != password
    assert security.new_app_username().startswith("pa_")

    token = security.create_app_token(app_id, "jwt-secret")
    assert security.decode_app_token(token, "jwt-secret") == app_id
    with pytest.raises(jwt.PyJWTError):
        security.decode_app_token(token, "wrong")
    with pytest.raises(ValueError):                                                      # dashboard and app tokens are not interchangeable
        security.decode_app_token(security.create_access_token(app_id, "jwt-secret"), "jwt-secret")
    with pytest.raises(ValueError):
        security.decode_access_token(token, "jwt-secret")

    signature = security.sign_callback(key, {"reference": "col_1", "status": "SUCCESSFUL"})
    assert jwt.decode(signature, key, algorithms=["HS256"])["reference"] == "col_1"
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(signature, "wrong-key", algorithms=["HS256"])


def test_campay_shaped_helpers():
    from app.services import compat

    assert compat.parse_amount("5000") == 5000 and compat.parse_amount(5000.0) == 5000 and compat.parse_amount(" 12 ") == 12
    for bad in ("abc", "0", "-5", "5.5", ""):
        with pytest.raises(ValueError):
            compat.parse_amount(bad)
    assert compat.campay_status("succeeded") == "SUCCESSFUL" and compat.campay_status("expired") == "FAILED"
    assert compat.campay_status("created") == "PENDING" and compat.campay_status("pending") == "PENDING"
    assert compat.ussd_for("MTN") == "*126#" and compat.ussd_for("ORANGE") == "#150*50#"

    class Tx:
        status = "succeeded"; public_id = "col_1"; amount = 5000; currency = "XAF"; operator = "MTN"
        provider_reference = "r"; merchant_reference = "ext"; description = "d"; failure_message = None

    params = compat.campay_params(Tx)
    assert params["status"] == "SUCCESSFUL" and params["external_reference"] == "ext" and params["amount"] == "5000" and "signature" not in params
    assert compat.campay_transaction(Tx)["reference"] == "col_1" and "reason" not in compat.campay_transaction(Tx)
