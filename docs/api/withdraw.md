# Withdraw (payout)

`POST /api/withdraw/`

Send money from your Paysawa balance to any MTN or Orange number.

Takes **amount + Paysawa's fee** from your available balance. The money is held while the operator processes the payout and returned to your balance if it fails.

**Authentication:** `Authorization: Token <token>` (token from [Get a token](token.md)).

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `amount` | string or number | yes | Whole XAF, at least 10. |
| `currency` | string | no | Only `XAF` (default). |
| `to` | string | yes | The receiver's phone number. |
| `description` | string | no | Shown in your history. |
| `external_reference` | string | no | **Your** reference. Returned in statuses and webhooks. |

## Examples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/api/withdraw/" \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "amount": "1000",
  "currency": "XAF",
  "to": "690000001",
  "description": "Refund",
  "external_reference": "refund-1001"
}'
```

### Python SDK

```python
from paysawa import Client

client = Client.from_env()

from paysawa import InsufficientFundsError

try:
    tx = client.withdraw(amount=1000, phone="690000001", description="Refund", external_reference="refund-1001")
except InsufficientFundsError:
    print("Not enough balance")
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Token YOUR_TOKEN",
}
payload = {
    "amount": "1000",
    "currency": "XAF",
    "to": "690000001",
    "description": "Refund",
    "external_reference": "refund-1001",
}

response = requests.post(f"{BASE}/api/withdraw/", json=payload, headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/withdraw/`, {
  method: "POST",
  headers: {
    "Authorization": "Token YOUR_TOKEN",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "amount": "1000",
    "currency": "XAF",
    "to": "690000001",
    "description": "Refund",
    "external_reference": "refund-1001"
  }),
});
console.log(response.status, await response.json());
```

## Responses

### 200 Withdrawal created

```json
{
  "reference": "pay_3c2b1a0f9e8d7c6b5a49",
  "status": "SUCCESSFUL",
  "amount": 1000,
  "currency": "XAF",
  "operator": "ORANGE"
}
```

### 402 Not enough balance

```json
{
  "message": "Available balance is 0 XAF, 1025 XAF needed (amount + fee).",
  "code": "insufficient_funds"
}
```

## Notes

A live withdrawal can answer `PENDING`; follow it like a collection. If the request itself fails with a network error, do not retry blindly: check by `external_reference` first.
