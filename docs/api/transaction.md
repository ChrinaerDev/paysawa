# Transaction status

`GET /api/transaction/{reference}/`

Get the latest state of a collection, a withdrawal or a payment link.

Use the `reference` returned by `collect`, `withdraw` or `get_payment_link`. `status` is `PENDING`, `SUCCESSFUL` or `FAILED`.
For a payment link reference (`cs_...`): `PENDING` means open, `SUCCESSFUL` paid, `FAILED` expired; when paid the answer also contains `payment_reference`.

**Authentication:** `Authorization: Token <token>` (token from [Get a token](token.md)).

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `reference` | string (path) | yes | `col_...`, `pay_...` or `cs_...`. |

## Examples

### cURL

```bash
curl "https://paysawa.onrender.com/api/transaction/col_8f3a1c2d4e5f6a7b8c9d/" \
  -H "Authorization: Token YOUR_TOKEN"
```

### Python SDK

```python
from paysawa import Client

client = Client.from_env()

tx = client.get_transaction("col_8f3a1c2d4e5f6a7b8c9d")
print(tx.status, tx.is_final)

# or wait until it is final:
tx = client.wait_for_transaction("col_8f3a1c2d4e5f6a7b8c9d", timeout=120)
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Token YOUR_TOKEN",
}

response = requests.get(f"{BASE}/api/transaction/col_8f3a1c2d4e5f6a7b8c9d/", headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/transaction/col_8f3a1c2d4e5f6a7b8c9d/`, {
  method: "GET",
  headers: {
    "Authorization": "Token YOUR_TOKEN"
  },
});
console.log(response.status, await response.json());
```

## Responses

### 200 Success

```json
{
  "reference": "col_8f3a1c2d4e5f6a7b8c9d",
  "status": "SUCCESSFUL",
  "amount": 5000,
  "currency": "XAF",
  "operator": "MTN",
  "code": "",
  "operator_reference": "op-123",
  "description": "Order 1001",
  "external_reference": "order-1001",
  "external_user": null
}
```

### 200 Failed payment

```json
{
  "reference": "col_1a2b3c4d5e6f7a8b9c0d",
  "status": "FAILED",
  "amount": 3000,
  "currency": "XAF",
  "operator": "MTN",
  "code": "",
  "operator_reference": "",
  "description": "",
  "external_reference": "order-1003",
  "external_user": null,
  "reason": "The payment provider rejected this request."
}
```

### 404 Unknown reference

```json
{
  "message": "Transaction not found.",
  "code": "not_found"
}
```

## Notes

Paysawa follows live payments with the operator for you, so this call returns fresh information. Poll every 2 to 3 seconds at most.
