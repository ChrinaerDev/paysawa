# Demo merchant app (second server, port 9000)

A separate server that uses a **Paysawa app's credentials** (app username, app password, webhook key) the way Paysawa
uses Campay's. It talks to Paysawa only through the Campay-style API (`/api/token/`, `/collect/`, `/withdraw/`,
`/transaction/{reference}/`, `/balance/`, `/get_payment_link/`) and receives Paysawa's signed webhooks.

## Run it

```bash
# 1) Paysawa server running on :8000 (uvicorn app.main:app), migration schema_003_apps.sql applied
# 2) create an app in the Paysawa CLI:  python -m cli  ->  a  ->  n   (copy username, password, webhook key)
cp merchant_app/.env.example merchant_app/.env      # paste the three values
pip install -r merchant_app/requirements.txt
python -m merchant_app                               # http://localhost:9000  (docs: /docs)
```

In the Paysawa CLI, set the app's webhook URL to `http://localhost:9000/webhooks/paysawa`
(test-mode apps may use localhost only if the Paysawa server has `ALLOW_PRIVATE_WEBHOOK_URLS=true`).
Without a webhook the demo still works: it polls Paysawa for every pending record.

## What to try
1. **Deposit** with `670000001` (test app): succeeds at once. `670000000` fails. A live app sends a real prompt.
2. **Withdrawal** to `690000001`: paid out of the app's merchant balance.
3. **Payment link**: open the link, pay on the Paysawa pay page, watch the row turn SUCCESSFUL and the webhook appear.
4. Break it on purpose: stop the Paysawa server mid-payment, give a wrong webhook key, or change a webhook parameter by hand
   (the demo rejects the webhook and logs why).

`merchant_app/paysawa_client.py` is a ~100 line client you can copy into your own project.
