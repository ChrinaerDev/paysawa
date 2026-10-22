# Collect (deposit)

`POST /api/collect/`

Ask a customer to pay you from their MTN or Orange Money account.

The customer receives a prompt on their phone and approves with their PIN. The money is credited to your Paysawa balance **minus Paysawa's fee**.

In **live** mode the answer is `PENDING` and the payment ends as `SUCCESSFUL` or `FAILED` when the customer answers: follow it with a webhook or `GET /api/transaction/{reference}/`. In **test** mode the answer is already final (see Test and live for the sandbox numbers).

**Authentication:** `Authorization: Token <token>` (token from [Get a token](token.md)).

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `amount` | string or number | yes | Whole XAF, at least 10. Example: `5000` or `"5000"`. |
| `currency` | string | no | Only `XAF` (default). |
| `from` | string | yes | The customer's phone number: `6XXXXXXXX`, `2376XXXXXXXX`; spaces and `+` are ignored. |
| `description` | string | no | Shown in your history. |
| `external_reference` | string | no | **Your** reference (order number...). Returned in statuses and webhooks. |

## Examples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/api/collect/" \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "amount": "5000",
  "currency": "XAF",
  "from": "670000001",
  "description": "Order 1001",
  "external_reference": "order-1001"
}'
```

### Python SDK

```python
from paysawa import Client

client = Client.from_env()

tx = client.collect(amount=5000, phone="670000001", description="Order 1001",
                    external_reference="order-1001", wait=True)
print(tx.reference, tx.status)
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Token YOUR_TOKEN",
}
payload = {
    "amount": "5000",
    "currency": "XAF",
    "from": "670000001",
    "description": "Order 1001",
    "external_reference": "order-1001",
}

response = requests.post(f"{BASE}/api/collect/", json=payload, headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/collect/`, {
  method: "POST",
  headers: {
    "Authorization": "Token YOUR_TOKEN",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "amount": "5000",
    "currency": "XAF",
    "from": "670000001",
    "description": "Order 1001",
    "external_reference": "order-1001"
  }),
});
console.log(response.status, await response.json());
```

## Responses

### 200 Request created

```json
{
  "reference": "col_8f3a1c2d4e5f6a7b8c9d",
  "ussd_code": "*126#",
  "operator": "MTN",
  "status": "PENDING"
}
```

### 422 Not a valid phone number

```json
{
  "message": "expected a Cameroonian mobile number like 6XXXXXXXX or +2376XXXXXXXX",
  "code": "invalid_phone"
}
```

### 403 Live mode not enabled

```json
{
  "message": "Live mode is not enabled for this account yet.",
  "code": "live_not_enabled"
}
```

## Notes

`ussd_code` is what the customer can dial to see the pending payment (`*126#` for MTN, `#150*50#` for Orange). The Apps API has no idempotency key: if a request fails with a network error, look the payment up by your `external_reference` before retrying.
