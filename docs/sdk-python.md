# Python SDK

```bash
pip install paysawa
```

Requires Python 3.9 or newer. Source and issues: the `paysawa-python` repository.

## Create a client

```python
from paysawa import Client

client = Client(
    app_username="pa_1a2b3c4d5e6f7a8b",
    app_password="YOUR_APP_PASSWORD",
    webhook_key="whk_...",
    base_url="https://paysawa.onrender.com/api/",     # or set the PAYSAWA_BASE_URL environment variable
)
```

Better, keep secrets out of code and read them from the environment:

```bash
export PAYSAWA_APP_USERNAME=pa_1a2b3c4d5e6f7a8b
export PAYSAWA_APP_PASSWORD=...
export PAYSAWA_WEBHOOK_KEY=whk_...
export PAYSAWA_BASE_URL=https://paysawa.onrender.com/api/
```

```python
client = Client.from_env()
```

The client gets and renews access tokens by itself. Use `with Client.from_env() as client:` to close connections when you are done.

## Collect

```python
tx = client.collect(amount=5000, phone="670000001", description="Order 1001", external_reference="order-1001")
print(tx.reference, tx.status, tx.operator)        # col_...  PENDING  MTN
```

Add `wait=True` to block until the payment is final (`timeout=120` seconds by default):

```python
tx = client.collect(5000, "670000001", "Order 1001", "order-1001", wait=True)
if tx.is_successful:
    ...
```

## Withdraw

```python
tx = client.withdraw(amount=1000, phone="690000001", description="Refund", external_reference="refund-1001")
```

Raises `InsufficientFundsError` if the amount plus the fee is more than your balance.

## Check a payment, wait for it

```python
tx = client.get_transaction("col_8f3a1c2d4e5f6a7b8c9d")
tx = client.wait_for_transaction("col_8f3a1c2d4e5f6a7b8c9d", timeout=120, interval=3)
```

`wait_for_transaction` raises `WaitTimeoutError` (with `.transaction`, the latest state) if the payment is still pending when time runs out.

A transaction behaves like a dictionary and like an object: `tx["status"]` and `tx.status` both work, plus `tx.is_pending`, `tx.is_successful`,
`tx.is_failed` and `tx.is_final`.

## Balance and payment links

```python
balance = client.get_balance()
print(balance.total_balance, balance.held_balance)

link = client.get_payment_link(amount=2000, description="Order 1002",
                               external_reference="order-1002", redirect_url="https://shop.example.com/thanks")
print(link.link)
```

## Webhooks

```python
event = client.verify_webhook(request.args.to_dict())     # raises WebhookVerificationError if the webhook is not authentic
```

Flask uses `request.args.to_dict()`, FastAPI `dict(request.query_params)`, Django `request.GET.dict()`. See [Webhooks](webhooks.md).

## Async

```python
from paysawa import AsyncClient

async with AsyncClient.from_env() as client:
    tx = await client.collect(5000, "670000001", "Order 1001", "order-1001", wait=True)
```

## Errors

Every error inherits from `PaysawaError` (`.message`, `.status`, `.code`):

| Exception | When |
|---|---|
| `AuthenticationError` | wrong app username or password |
| `PermissionDeniedError` | live mode not enabled, account suspended |
| `InvalidRequestError` | bad amount or phone, unknown reference, limits |
| `InsufficientFundsError` | withdrawal larger than the balance (a kind of `InvalidRequestError`) |
| `RateLimitError` | too many requests |
| `ServerError`, `NetworkError` | Paysawa busy or unreachable |
| `WaitTimeoutError` | `wait_for_transaction` gave up |
| `WebhookVerificationError` | the webhook is not authentic: ignore it |

```python
from paysawa import InsufficientFundsError, PaysawaError

try:
    client.withdraw(100000, "690000001")
except InsufficientFundsError:
    ...
except PaysawaError as exc:
    print(exc.status, exc.code, exc.message)
```

**Payments are never retried automatically**, so a retry can never charge a customer twice. Reads are retried twice on network errors and 5xx.

## Updating

```bash
pip install --upgrade paysawa
pip show paysawa          # the installed version
```
