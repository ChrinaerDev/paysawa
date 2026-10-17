"""Extended checks: outgoing webhooks, failed-payout refund, retry behaviour, tick job.

Prerequisites (same machine as the server):
  * server started with   ALLOW_PRIVATE_WEBHOOK_URLS=true   (so test-mode webhooks may target localhost)
  * INTERNAL_TICK_SECRET in your environment or .env (same value the server uses)

    BASE_URL=http://localhost:8000 python -m scripts.smoke_test_extended
    ... --wait-retry      also waits ~65 s to prove a failed delivery is retried by /internal/tick

It starts a tiny webhook receiver on 127.0.0.1, registers it for the smoke-test merchant, and removes
the endpoint and revokes the API key at the end (even after a failure).
"""
import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

import scripts.smoke_test as st
from app.config import get_settings
from app.security import verify_signature
from scripts.smoke_test import Abort, brief, call, check, expect


class Receiver:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.fail_next = 0
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                with outer._lock:
                    outer.events.append({"body": body, "signature": self.headers.get("X-Paysawa-Signature", ""),
                                         "event": self.headers.get("X-Paysawa-Event", "")})
                    fail = outer.fail_next > 0
                    if fail:
                        outer.fail_next -= 1
                self.send_response(500 if fail else 200)
                self.end_headers()

            def log_message(self, *args):  # silence
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def wait_for(self, event_type: str, tx_id: str, timeout: float = 12.0, skip: int = 0) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                matches = [e for e in self.events if e["event"] == event_type and json.loads(e["body"])["data"]["id"] == tx_id]
            if len(matches) > skip:
                return matches[skip]
            time.sleep(0.3)
        return None

    def stop(self) -> None:
        self.server.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-retry", action="store_true")
    args = parser.parse_args()

    tick_secret = get_settings().internal_tick_secret
    receiver = Receiver()
    http = httpx.Client(base_url=st.BASE, timeout=st.TIMEOUT, limits=httpx.Limits(max_keepalive_connections=0))
    dash: dict = {}
    key_id = endpoint_id = None
    try:
        expect("server reachable", call(http, "GET", "/health"), 200, critical=True)
        r = call(http, "POST", "/auth/login", json={"email": st.EMAIL, "password": st.PASSWORD})
        if r.status_code == 401:
            r = call(http, "POST", "/auth/signup", json={"name": "Smoke Test", "email": st.EMAIL, "password": st.PASSWORD})
            data = expect("signup (first run only)", r, 201, critical=True)
        else:
            data = expect("login (reusing the smoke-test merchant)", r, 200, critical=True)
        dash = {"Authorization": f"Bearer {data['token']}"}
        data = expect("create test key", call(http, "POST", "/me/api-keys", json={"mode": "test", "label": "smoke-ext"}, headers=dash), 201, critical=True)
        key_id = data["id"]
        api = {"Authorization": f"Bearer {data['secret']}"}

        r = call(http, "POST", "/me/webhook-endpoints", json={"mode": "test", "url": f"http://127.0.0.1:{receiver.port}/hook", "events": []}, headers=dash)
        if r.status_code == 422:
            raise Abort("server refused a localhost webhook URL. Restart it with ALLOW_PRIVATE_WEBHOOK_URLS=true in .env")
        data = expect("webhook endpoint registered", r, 201, critical=True)
        endpoint_id, secret = data["id"], data["signing_secret"]

        def balance() -> dict:
            return call(http, "GET", "/v1/balance", headers=api).json()

        # ---- 1. webhook delivered + signature valid
        tx = expect("collection created", call(http, "POST", "/v1/collections", json={"amount": 5000, "phone": "670000001"}, headers=api), 201,
                    lambda j: j["status"] == "succeeded", critical=True)
        got = receiver.wait_for("collection.succeeded", tx["id"])
        check("webhook collection.succeeded delivered within 12 s", got is not None, "nothing received (is the server running with ALLOW_PRIVATE_WEBHOOK_URLS=true?)")
        if got:
            check("webhook signature verifies with the endpoint secret", verify_signature(secret, got["body"], got["signature"]), "bad signature")
            check("tampered body fails verification", not verify_signature(secret, got["body"] + b" ", got["signature"]), "tampered body accepted")
            payload = json.loads(got["body"])
            check("payload carries the transaction", payload["type"] == "collection.succeeded" and payload["data"]["amount"] == 5000, str(payload)[:160])

        # ---- 2. failed payout releases the hold
        before = balance()
        px = expect("payout to a failing number is created", call(http, "POST", "/v1/payouts", json={"amount": 1000, "phone": "670000000"}, headers=api), 201,
                    lambda j: j["status"] == "failed", critical=True)
        after = balance()
        check("failed payout: available balance restored and nothing left held",
              after["available"] == before["available"] and after["held"] == before["held"],
              f"available {after['available'] - before['available']:+}, held {after['held'] - before['held']:+}")
        check("webhook payout.failed delivered", receiver.wait_for("payout.failed", px["id"]) is not None, "nothing received")

        # ---- 3. retry behaviour: receiver answers 500 once
        receiver.fail_next = 1
        tx2 = expect("collection created (receiver will answer 500 once)", call(http, "POST", "/v1/collections", json={"amount": 3000, "phone": "670000002"}, headers=api), 201, critical=True)
        check("first delivery attempt reached the receiver", receiver.wait_for("collection.succeeded", tx2["id"]) is not None, "nothing received")
        time.sleep(1.0)
        rows = call(http, "GET", "/me/webhook-deliveries?limit=20", headers=dash).json()["data"]
        retrying = [d for d in rows if d["status"] == "pending" and d["attempts"] == 1 and d["last_status_code"] == 500]
        check("failed delivery is queued for retry (pending, attempts=1, HTTP 500 recorded)", len(retrying) >= 1, str(rows[:2]))

        # ---- 4. tick job
        if not tick_secret:
            check("tick job", False, "INTERNAL_TICK_SECRET not found in env/.env")
        else:
            t = expect("tick job runs", call(http, "POST", "/internal/tick", headers={"X-Internal-Secret": tick_secret}), 200,
                       lambda j: {"deliveries", "reconciled", "expired", "balance_check"} <= set(j))
            if t:
                print(f"     tick said: {json.dumps(t)}")
            expect("tick refuses a wrong secret", call(http, "POST", "/internal/tick", headers={"X-Internal-Secret": "nope"}), 401)

            if args.wait_retry:
                print("     waiting 65 s for the retry to become due ...")
                time.sleep(65)
                call(http, "POST", "/internal/tick", headers={"X-Internal-Secret": tick_secret})
                check("retried delivery reached the receiver on the second attempt",
                      receiver.wait_for("collection.succeeded", tx2["id"], timeout=10, skip=1) is not None, "no second delivery")
            else:
                print("     (skipped: retry-after-tick check, add --wait-retry to run it, takes ~65 s)")

    except Abort as exc:
        check("run", False, str(exc))
        print(f"\nABORTED: {exc}")
    finally:
        for method, path in ((("DELETE", f"/me/webhook-endpoints/{endpoint_id}") if endpoint_id else None),
                             (("DELETE", f"/me/api-keys/{key_id}") if key_id else None)):
            if path and dash:
                try:
                    r = http.request(method, path, headers=dash)
                    print(f"cleanup: {path.split('/')[2]} removed" if r.status_code == 200 else f"cleanup: could not remove {path} ({brief(r)})")
                except httpx.HTTPError:
                    print(f"cleanup: could not reach the server to remove {path}")
        receiver.stop()
        http.close()

    print(f"\n{'ALL PASSED' if not st.failures else str(st.failures) + ' FAILED'}")
    sys.exit(1 if st.failures else 0)


if __name__ == "__main__":
    main()
