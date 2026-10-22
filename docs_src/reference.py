"""Structured API reference: one entry per endpoint. build.py turns these into Markdown files and website data."""

AUTH_TOKEN = "Authorization: Token YOUR_TOKEN"
AUTH_KEY = "Authorization: Bearer sk_test_YOUR_KEY"

TX_EXAMPLE = {
    "id": "col_8f3a1c2d4e5f6a7b8c9d", "object": "collection", "mode": "test", "status": "succeeded", "amount": 5000, "fee": 125,
    "currency": "XAF", "phone_number": "237670000001", "operator": "MTN", "description": "Order 1001",
    "merchant_reference": "order-1001", "failure_code": None, "failure_message": None, "metadata": {}, "checkout_session": None,
    "created_at": "2026-10-18T09:15:02.123456+00:00", "completed_at": "2026-10-18T09:15:02.456789+00:00",
}
SESSION_EXAMPLE = {
    "id": "cs_5d4c3b2a1f0e9d8c7b6a", "object": "checkout_session", "mode": "test", "status": "open", "amount": 2000, "currency": "XAF",
    "description": "Order 1002", "merchant_reference": "order-1002", "redirect_url": "https://shop.example.com/thanks", "metadata": {},
    "url": "https://YOUR-PAYSAWA-URL/pay/cs_5d4c3b2a1f0e9d8c7b6a", "expires_at": "2026-10-18T10:15:02+00:00", "expires_in_seconds": 3600,
    "created_at": "2026-10-18T09:15:02+00:00", "paid_at": None,
}


def p(name, type_, required, description):
    return {"name": name, "type": type_, "required": required, "description": description}


GROUP_APPS = "Apps API"
GROUP_V1 = "API v1"

ENDPOINTS = [
    {
        "id": "token", "group": GROUP_APPS, "title": "Get a token", "method": "POST", "path": "/api/token/", "auth": "none",
        "summary": "Exchange your app username and password for an access token.",
        "description": "Call this first. The token is valid for `expires_in` seconds (one hour); reuse it, and ask for a new one when a call answers `401`.\n"
                       "Send it afterwards as `Authorization: Token <token>`.",
        "params": [p("username", "string", True, "The app username, like `pa_1a2b3c4d5e6f7a8b`."),
                   p("password", "string", True, "The app password.")],
        "body": {"username": "pa_1a2b3c4d5e6f7a8b", "password": "YOUR_APP_PASSWORD"},
        "responses": [
            {"status": 200, "title": "Success", "body": {"token": "eyJhbGciOiJIUzI1NiIs...", "expires_in": 3600}},
            {"status": 401, "title": "Wrong credentials", "body": {"message": "Invalid app username or password.", "code": "invalid_credentials"}},
            {"status": 429, "title": "Too many attempts", "body": {"message": "Too many requests, slow down.", "code": "rate_limited"}},
        ],
        "notes": "Token requests are limited to 20 per 5 minutes per username and address.",
        "sdk": "# The SDK gets and renews tokens for you.\nfrom paysawa import Client\n\nclient = Client.from_env()\nprint(client.get_balance())",
    },
    {
        "id": "collect", "group": GROUP_APPS, "title": "Collect (deposit)", "method": "POST", "path": "/api/collect/", "auth": "token",
        "summary": "Ask a customer to pay you from their MTN or Orange Money account.",
        "description": "The customer receives a prompt on their phone and approves with their PIN. The money is credited to your Paysawa balance **minus Paysawa's fee**.\n\n"
                       "In **live** mode the answer is `PENDING` and the payment ends as `SUCCESSFUL` or `FAILED` when the customer answers: follow it with a webhook "
                       "or `GET /api/transaction/{reference}/`. In **test** mode the answer is already final (see Test and live for the sandbox numbers).",
        "params": [p("amount", "string or number", True, "Whole XAF, at least 10. Example: `5000` or `\"5000\"`."),
                   p("currency", "string", False, "Only `XAF` (default)."),
                   p("from", "string", True, "The customer's phone number: `6XXXXXXXX`, `2376XXXXXXXX`; spaces and `+` are ignored."),
                   p("description", "string", False, "Shown in your history."),
                   p("external_reference", "string", False, "**Your** reference (order number...). Returned in statuses and webhooks.")],
        "body": {"amount": "5000", "currency": "XAF", "from": "670000001", "description": "Order 1001", "external_reference": "order-1001"},
        "responses": [
            {"status": 200, "title": "Request created", "body": {"reference": "col_8f3a1c2d4e5f6a7b8c9d", "ussd_code": "*126#", "operator": "MTN", "status": "PENDING"}},
            {"status": 422, "title": "Not a valid phone number", "body": {"message": "expected a Cameroonian mobile number like 6XXXXXXXX or +2376XXXXXXXX", "code": "invalid_phone"}},
            {"status": 403, "title": "Live mode not enabled", "body": {"message": "Live mode is not enabled for this account yet.", "code": "live_not_enabled"}},
        ],
        "notes": "`ussd_code` is what the customer can dial to see the pending payment (`*126#` for MTN, `#150*50#` for Orange). "
                 "The Apps API has no idempotency key: if a request fails with a network error, look the payment up by your `external_reference` before retrying.",
        "sdk": "tx = client.collect(amount=5000, phone=\"670000001\", description=\"Order 1001\",\n                    external_reference=\"order-1001\", wait=True)\nprint(tx.reference, tx.status)",
    },
    {
        "id": "withdraw", "group": GROUP_APPS, "title": "Withdraw (payout)", "method": "POST", "path": "/api/withdraw/", "auth": "token",
        "summary": "Send money from your Paysawa balance to any MTN or Orange number.",
        "description": "Takes **amount + Paysawa's fee** from your available balance. The money is held while the operator processes the payout and returned to your balance if it fails.",
        "params": [p("amount", "string or number", True, "Whole XAF, at least 10."),
                   p("currency", "string", False, "Only `XAF` (default)."),
                   p("to", "string", True, "The receiver's phone number."),
                   p("description", "string", False, "Shown in your history."),
                   p("external_reference", "string", False, "**Your** reference. Returned in statuses and webhooks.")],
        "body": {"amount": "1000", "currency": "XAF", "to": "690000001", "description": "Refund", "external_reference": "refund-1001"},
        "responses": [
            {"status": 200, "title": "Withdrawal created", "body": {"reference": "pay_3c2b1a0f9e8d7c6b5a49", "status": "SUCCESSFUL", "amount": 1000, "currency": "XAF", "operator": "ORANGE"}},
            {"status": 402, "title": "Not enough balance", "body": {"message": "Available balance is 0 XAF, 1025 XAF needed (amount + fee).", "code": "insufficient_funds"}},
        ],
        "notes": "A live withdrawal can answer `PENDING`; follow it like a collection. If the request itself fails with a network error, do not retry blindly: check by `external_reference` first.",
        "sdk": "from paysawa import InsufficientFundsError\n\ntry:\n    tx = client.withdraw(amount=1000, phone=\"690000001\", description=\"Refund\", external_reference=\"refund-1001\")\nexcept InsufficientFundsError:\n    print(\"Not enough balance\")",
    },
    {
        "id": "transaction", "group": GROUP_APPS, "title": "Transaction status", "method": "GET", "path": "/api/transaction/{reference}/", "auth": "token",
        "example_path": "/api/transaction/col_8f3a1c2d4e5f6a7b8c9d/",
        "summary": "Get the latest state of a collection, a withdrawal or a payment link.",
        "description": "Use the `reference` returned by `collect`, `withdraw` or `get_payment_link`. `status` is `PENDING`, `SUCCESSFUL` or `FAILED`.\n"
                       "For a payment link reference (`cs_...`): `PENDING` means open, `SUCCESSFUL` paid, `FAILED` expired; when paid the answer also contains `payment_reference`.",
        "params": [p("reference", "string (path)", True, "`col_...`, `pay_...` or `cs_...`.")],
        "responses": [
            {"status": 200, "title": "Success", "body": {"reference": "col_8f3a1c2d4e5f6a7b8c9d", "status": "SUCCESSFUL", "amount": 5000, "currency": "XAF",
                                                          "operator": "MTN", "code": "", "operator_reference": "op-123", "description": "Order 1001",
                                                          "external_reference": "order-1001", "external_user": None}},
            {"status": 200, "title": "Failed payment", "body": {"reference": "col_1a2b3c4d5e6f7a8b9c0d", "status": "FAILED", "amount": 3000, "currency": "XAF",
                                                                 "operator": "MTN", "code": "", "operator_reference": "", "description": "", "external_reference": "order-1003",
                                                                 "external_user": None, "reason": "The payment provider rejected this request."}},
            {"status": 404, "title": "Unknown reference", "body": {"message": "Transaction not found.", "code": "not_found"}},
        ],
        "notes": "Paysawa follows live payments with the operator for you, so this call returns fresh information. Poll every 2 to 3 seconds at most.",
        "sdk": "tx = client.get_transaction(\"col_8f3a1c2d4e5f6a7b8c9d\")\nprint(tx.status, tx.is_final)\n\n# or wait until it is final:\ntx = client.wait_for_transaction(\"col_8f3a1c2d4e5f6a7b8c9d\", timeout=120)",
    },
    {
        "id": "balance", "group": GROUP_APPS, "title": "Balance", "method": "GET", "path": "/api/balance/", "auth": "token",
        "summary": "Your available balance in this app's mode (test or live).",
        "description": "`total_balance` is what you can withdraw. `held_balance` is money reserved for withdrawals still being processed. "
                       "Paysawa keeps one balance per account, so `mtn_balance` and `orange_balance` are always `null`.",
        "params": [],
        "responses": [{"status": 200, "title": "Success", "body": {"total_balance": 4875, "mtn_balance": None, "orange_balance": None, "held_balance": 0, "currency": "XAF"}}],
        "notes": "",
        "sdk": "balance = client.get_balance()\nprint(balance.total_balance, balance.held_balance)",
    },
    {
        "id": "get-payment-link", "group": GROUP_APPS, "title": "Payment link", "method": "POST", "path": "/api/get_payment_link/", "auth": "token",
        "summary": "Create a link to the hosted pay page for one amount.",
        "description": "Send the `link` to your customer. They enter their phone number on the Paysawa pay page and approve on their phone. The link is valid for 60 minutes and allows 3 attempts. "
                       "Your app's webhook is called when the payment finishes.",
        "params": [p("amount", "string or number", True, "Whole XAF, at least 10."),
                   p("currency", "string", False, "Only `XAF` (default)."),
                   p("description", "string", False, "Shown on the pay page."),
                   p("external_reference", "string", False, "**Your** reference. Returned in the webhook."),
                   p("redirect_url", "string", False, "Where to send the customer after a successful payment. `https` and public in live mode."),
                   p("from", "string", False, "Accepted and ignored for now."),
                   p("failure_redirect_url", "string", False, "Accepted and ignored for now.")],
        "body": {"amount": "2000", "currency": "XAF", "description": "Order 1002", "external_reference": "order-1002", "redirect_url": "https://shop.example.com/thanks"},
        "responses": [
            {"status": 200, "title": "Link created", "body": {"link": "https://YOUR-PAYSAWA-URL/pay/cs_5d4c3b2a1f0e9d8c7b6a", "reference": "cs_5d4c3b2a1f0e9d8c7b6a"}},
            {"status": 422, "title": "Redirect URL refused", "body": {"message": "https is required in live mode", "code": "invalid_redirect_url"}},
        ],
        "notes": "Do not trust the customer's return to your `redirect_url` as proof of payment: use the webhook or the transaction status.",
        "sdk": "link = client.get_payment_link(amount=2000, description=\"Order 1002\",\n                               external_reference=\"order-1002\",\n                               redirect_url=\"https://shop.example.com/thanks\")\nprint(link.link)",
    },
    {
        "id": "v1-create-collection", "group": GROUP_V1, "title": "Create a collection", "method": "POST", "path": "/v1/collections", "auth": "apikey",
        "summary": "Ask a customer to pay you (API key version).",
        "description": "Same operation as `collect` in the Apps API, with JSON objects, an `Idempotency-Key` header and metadata. The mode (test or live) comes from the key.",
        "headers": [p("Idempotency-Key", "string", False, "Any unique string. Sending the same key again returns the original collection (`200`) instead of charging twice; the same key with other parameters answers `409`.")],
        "params": [p("amount", "integer", True, "Whole XAF, at least 10."),
                   p("phone", "string", True, "The customer's phone number."),
                   p("description", "string", False, "Up to 160 characters."),
                   p("merchant_reference", "string", False, "**Your** reference, up to 100 characters."),
                   p("metadata", "object", False, "Your own data, up to 2000 characters, returned unchanged.")],
        "body": {"amount": 5000, "phone": "670000001", "description": "Order 1001", "merchant_reference": "order-1001"},
        "responses": [{"status": 201, "title": "Created", "body": TX_EXAMPLE},
                      {"status": 409, "title": "Idempotency conflict", "body": {"error": {"code": "idempotency_conflict", "message": "This Idempotency-Key was already used with different parameters."}}}],
        "notes": "`status` is `pending`, `succeeded`, `failed` or `expired`. Fields `fee` and `amount` are in XAF.",
        "extra_headers": ["Idempotency-Key: order-1001-attempt-1"],
    },
    {
        "id": "v1-get-collection", "group": GROUP_V1, "title": "Get a collection", "method": "GET", "path": "/v1/collections/{id}", "auth": "apikey",
        "example_path": "/v1/collections/col_8f3a1c2d4e5f6a7b8c9d",
        "summary": "Read a collection.", "description": "Pending live collections are refreshed with the operator when you read them.",
        "params": [p("id", "string (path)", True, "The `id` of the collection (`col_...`).")],
        "responses": [{"status": 200, "title": "Success", "body": TX_EXAMPLE}], "notes": "",
    },
    {
        "id": "v1-create-payout", "group": GROUP_V1, "title": "Create a payout", "method": "POST", "path": "/v1/payouts", "auth": "apikey",
        "summary": "Send money from your balance to a phone (API key version).",
        "description": "Takes amount + fee from your available balance (held first, returned if it fails). Supports the `Idempotency-Key` header like collections.",
        "headers": [p("Idempotency-Key", "string", False, "Unique string for safe retries.")],
        "params": [p("amount", "integer", True, "Whole XAF, at least 10."), p("phone", "string", True, "The receiver's phone number."),
                   p("description", "string", False, "Up to 160 characters."), p("merchant_reference", "string", False, "**Your** reference."),
                   p("metadata", "object", False, "Your own data.")],
        "body": {"amount": 1000, "phone": "690000001", "description": "Refund", "merchant_reference": "refund-1001"},
        "responses": [{"status": 201, "title": "Created", "body": {**TX_EXAMPLE, "id": "pay_3c2b1a0f9e8d7c6b5a49", "object": "payout", "amount": 1000, "fee": 25, "operator": "ORANGE", "phone_number": "237690000001"}},
                      {"status": 402, "title": "Not enough balance", "body": {"error": {"code": "insufficient_funds", "message": "Available balance is 0 XAF, 1025 XAF needed (amount + fee)."}}}],
        "notes": "",
        "extra_headers": ["Idempotency-Key: refund-1001-attempt-1"],
    },
    {
        "id": "v1-get-payout", "group": GROUP_V1, "title": "Get a payout", "method": "GET", "path": "/v1/payouts/{id}", "auth": "apikey",
        "example_path": "/v1/payouts/pay_3c2b1a0f9e8d7c6b5a49", "summary": "Read a payout.", "description": "",
        "params": [p("id", "string (path)", True, "The `id` of the payout (`pay_...`).")],
        "responses": [{"status": 200, "title": "Success", "body": {**TX_EXAMPLE, "id": "pay_3c2b1a0f9e8d7c6b5a49", "object": "payout"}}], "notes": "",
    },
    {
        "id": "v1-balance", "group": GROUP_V1, "title": "Balance", "method": "GET", "path": "/v1/balance", "auth": "apikey",
        "summary": "Your balance in the key's mode.", "description": "", "params": [],
        "responses": [{"status": 200, "title": "Success", "body": {"mode": "test", "currency": "XAF", "available": 4875, "held": 0}}], "notes": "",
    },
    {
        "id": "v1-list-transactions", "group": GROUP_V1, "title": "List transactions", "method": "GET", "path": "/v1/transactions", "auth": "apikey",
        "summary": "Your collections and payouts, newest first.", "description": "",
        "params": [p("type", "string (query)", False, "`collection` or `payout`."),
                   p("status", "string (query)", False, "`pending`, `succeeded`, `failed` or `expired`."),
                   p("limit", "integer (query)", False, "1 to 100, default 50."), p("offset", "integer (query)", False, "Default 0.")],
        "query": {"status": "succeeded", "limit": 20},
        "responses": [{"status": 200, "title": "Success", "body": {"data": [TX_EXAMPLE], "limit": 20, "offset": 0}}], "notes": "",
    },
    {
        "id": "v1-create-checkout-session", "group": GROUP_V1, "title": "Create a checkout session", "method": "POST", "path": "/v1/checkout-sessions", "auth": "apikey",
        "summary": "Create a payment link to the hosted pay page (API key version).",
        "description": "Like the Apps API payment link, with a configurable lifetime.",
        "params": [p("amount", "integer", True, "Whole XAF, at least 10."), p("description", "string", False, "Shown on the pay page."),
                   p("merchant_reference", "string", False, "**Your** reference."),
                   p("redirect_url", "string", False, "Where to send the customer after payment. `https` and public in live mode."),
                   p("expires_in_minutes", "integer", False, "1 to 1440, default 60."), p("metadata", "object", False, "Your own data.")],
        "body": {"amount": 2000, "description": "Order 1002", "merchant_reference": "order-1002", "redirect_url": "https://shop.example.com/thanks", "expires_in_minutes": 60},
        "responses": [{"status": 201, "title": "Created", "body": SESSION_EXAMPLE}], "notes": "Send `url` to your customer. Times are UTC; use `expires_in_seconds` for countdowns.",
    },
    {
        "id": "v1-get-checkout-session", "group": GROUP_V1, "title": "Get a checkout session", "method": "GET", "path": "/v1/checkout-sessions/{id}", "auth": "apikey",
        "example_path": "/v1/checkout-sessions/cs_5d4c3b2a1f0e9d8c7b6a", "summary": "Read a checkout session.", "description": "`status` is `open`, `paid` or `expired`.",
        "params": [p("id", "string (path)", True, "The `id` of the session (`cs_...`).")],
        "responses": [{"status": 200, "title": "Success", "body": {**SESSION_EXAMPLE, "status": "paid", "paid_at": "2026-10-18T09:20:11+00:00"}}], "notes": "",
    },
]

GROUP_ORDER = ["Introduction", GROUP_APPS, GROUP_V1, "Webhooks", "Payment links", "SDKs", "Reference"]
