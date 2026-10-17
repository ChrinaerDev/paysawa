"""End-to-end check against a running server in TEST mode (simulated provider).

    BASE_URL=http://localhost:8000 python -m scripts.smoke_test            # normal run
    BASE_URL=http://localhost:8000 python -m scripts.smoke_test --with-pending   # also leaves one pending tx

Re-runnable by design: it reuses ONE fixed merchant (smoketest@paysawa.local) instead of creating a new
one each run, uses unique idempotency keys per run, compares balances as differences from the starting
balance, and revokes the API key it created when it finishes (even after a failure).
What stays behind is only the sandbox ledger history of that one merchant: the ledger is append-only by
design (database triggers refuse deletes), so transactions cannot be erased.
"""
import argparse
import os
import sys
import time
import uuid

import httpx

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = float(os.environ.get("SMOKE_TIMEOUT", "45"))  # Neon may need a few seconds to wake up
EMAIL = "smoketest@paysawa.local"
PASSWORD = "smoke-test-pass-1"
RUN = uuid.uuid4().hex[:8]
failures = 0


class Abort(Exception):
    """Stops the run with a one-line explanation (no traceback)."""


def check(name: str, ok: bool, detail: str = "") -> bool:
    global failures
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"))
    failures += 0 if ok else 1
    return ok


def brief(r: httpx.Response) -> str:
    try:
        err = r.json().get("error")
        if err:
            return f"HTTP {r.status_code} {err.get('code')}: {err.get('message')}"
    except Exception:
        pass
    return f"HTTP {r.status_code} {r.text[:120]!r}"


def call(http: httpx.Client, method: str, path: str, **kw) -> httpx.Response:
    for attempt in range(3):
        try:
            return http.request(method, path, **kw)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            if attempt == 2:
                raise Abort(f"cannot connect to {BASE}. Is the server running? (uvicorn app.main:app)")
            time.sleep(2)
        except httpx.ReadTimeout:
            if method == "GET" and attempt < 2:
                time.sleep(2)
                continue
            raise Abort(
                f"{method} {path} got no answer within {TIMEOUT:.0f}s. The server or the database is stuck: "
                "look at the uvicorn console for the error, then restart the server and re-run."
            )
        except httpx.HTTPError as exc:
            raise Abort(f"{method} {path} failed: {type(exc).__name__}")
    raise Abort("unreachable")


def expect(name: str, r: httpx.Response, status: int, test=None, *, critical: bool = False):
    ok = r.status_code == status
    if ok and test is not None:
        try:
            ok = bool(test(r.json()))
        except Exception:
            ok = False
    check(name, ok, brief(r) if r.status_code != status else f"unexpected body: {r.text[:160]!r}")
    if not ok and critical:
        raise Abort(f"'{name}' failed, later steps depend on it")
    return r.json() if ok else None


def fee(amount: int, bps: int) -> int:  # same rule as app/fees.py
    if bps <= 0 or amount <= 1:
        return 0
    return min((amount * bps + 9_999) // 10_000, amount - 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-pending", action="store_true", help="also create a collection that stays pending forever")
    args = parser.parse_args()

    # no keep-alive: after a server-side 500 uvicorn closes the socket, and a reused connection
    # would then fail with a confusing ReadError on the next request
    http = httpx.Client(base_url=BASE, timeout=TIMEOUT, limits=httpx.Limits(max_keepalive_connections=0))
    dash: dict = {}
    key_id = None
    try:
        r = call(http, "GET", "/health")
        expect("server reachable", r, 200, critical=True)

        # first DB-touching call: also wakes Neon if it was suspended
        r = call(http, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if r.status_code == 401:
            r = call(http, "POST", "/auth/signup", json={"name": "Smoke Test", "email": EMAIL, "password": PASSWORD})
            data = expect("signup (first run only)", r, 201, critical=True)
        else:
            data = expect("login (reusing the smoke-test merchant)", r, 200, critical=True)
        dash = {"Authorization": f"Bearer {data['token']}"}
        bps = data["merchant"]["fees_bps"]

        data = expect("create test key", call(http, "POST", "/me/api-keys", json={"mode": "test", "label": f"smoke-{RUN}"}, headers=dash), 201, critical=True)
        key_id = data["id"]
        api = {"Authorization": f"Bearer {data['secret']}"}

        start = expect("read starting balance", call(http, "GET", "/v1/balance", headers=api), 200, critical=True)
        base_available, base_held = start["available"], start["held"]

        def balance() -> dict:
            return call(http, "GET", "/v1/balance", headers=api).json()

        # ---- collection + idempotency
        idem = {**api, "Idempotency-Key": f"{RUN}-k1"}
        body = {"amount": 5000, "phone": "670000001", "description": "smoke"}
        first = expect("collection created and settled", call(http, "POST", "/v1/collections", json=body, headers=idem), 201,
                       lambda j: j["status"] == "succeeded")
        first_id = first["id"] if first else None
        expect("idempotent replay returns the same transaction", call(http, "POST", "/v1/collections", json=body, headers=idem), 200,
               lambda j: j["id"] == first_id)
        expect("idempotency conflict is rejected", call(http, "POST", "/v1/collections", json={**body, "amount": 6000}, headers=idem), 409)

        credit1 = 5000 - fee(5000, bps["collection"])
        b = balance()
        check(f"balance rose by {credit1} (5000 minus fee)", b["available"] - base_available == credit1, f"got +{b['available'] - base_available}")

        # ---- failing number
        expect("number ending 0000 fails", call(http, "POST", "/v1/collections", json={"amount": 3000, "phone": "670000000"}, headers=api), 201,
               lambda j: j["status"] == "failed")
        if args.with_pending:
            expect("number ending 9999 stays pending", call(http, "POST", "/v1/collections", json={"amount": 3000, "phone": "670009999"}, headers=api), 201,
                   lambda j: j["status"] == "pending")
        b = balance()
        check("failed/pending collections did not change the balance", b["available"] - base_available == credit1, f"got +{b['available'] - base_available}")

        # ---- payouts (Orange number), then an impossible one
        expect("payout to an Orange number succeeds", call(http, "POST", "/v1/payouts", json={"amount": 1000, "phone": "690000001"}, headers=api), 201,
               lambda j: j["status"] == "succeeded")
        debit = 1000 + fee(1000, bps["payout"])
        b = balance()
        check(f"balance fell by {debit} (1000 plus fee), nothing left held",
              b["available"] - base_available == credit1 - debit and b["held"] == base_held,
              f"available {b['available'] - base_available:+}, held {b['held'] - base_held:+}")
        too_much = b["available"] + 1000
        expect("payout above the balance is refused", call(http, "POST", "/v1/payouts", json={"amount": too_much, "phone": "670000001"}, headers=api), 402)

        # ---- pay page backend
        cs = expect("checkout session created", call(http, "POST", "/v1/checkout-sessions", json={"amount": 2000, "description": "Pay page test", "merchant_reference": f"order-{RUN}"}, headers=api),
                    201, critical=True)
        sid = cs["id"]
        expect("public session view is open", call(http, "GET", f"/gate/sessions/{sid}"), 200, lambda j: j["status"] == "open")
        expect("paying on the gate settles the session", call(http, "POST", f"/gate/sessions/{sid}/pay", json={"phone": "655000002"}), 200,
               lambda j: j["status"] == "paid")
        credit2 = 2000 - fee(2000, bps["collection"])
        b = balance()
        check(f"balance rose by {credit2} from the checkout payment", b["available"] - base_available == credit1 - debit + credit2,
              f"got {b['available'] - base_available:+}")

        expect("transaction list works", call(http, "GET", "/v1/transactions?limit=5", headers=api), 200, lambda j: len(j["data"]) >= 1)

    except Abort as exc:
        check("run", False, str(exc))
        print(f"\nABORTED: {exc}")
    finally:
        if key_id and dash:
            try:  # cleanup: never leave a working key behind
                r = http.delete(f"/me/api-keys/{key_id}", headers=dash)
                print("cleanup: test key revoked" if r.status_code == 200 else f"cleanup: could not revoke key ({brief(r)})")
            except httpx.HTTPError:
                print("cleanup: could not revoke the key (server not answering); revoke it from the dashboard later")
        http.close()

    print(f"\n{'ALL PASSED' if not failures else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
