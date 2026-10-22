# Create a payout

`POST /v1/payouts`

Send money from your balance to a phone (API key version).

Takes amount + fee from your available balance (held first, returned if it fails). Supports the `Idempotency-Key` header like collections.

**Authentication:** `Authorization: Bearer sk_test_...` or `sk_live_...` (secret API key).

## Headers

| Name | Type | Required | Description |
|---|---|---|---|
| `Idempotency-Key` | string | no | Unique string for safe retries. |

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `amount` | integer | yes | Whole XAF, at least 10. |
| `phone` | string | yes | The receiver's phone number. |
| `description` | string | no | Up to 160 characters. |
| `merchant_reference` | string | no | **Your** reference. |
| `metadata` | object | no | Your own data. |

## Examples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/v1/payouts" \
  -H "Authorization: Bearer sk_test_YOUR_KEY" \
  -H "Idempotency-Key: refund-1001-attempt-1" \
  -H "Content-Type: application/json" \
  -d '{
  "amount": 1000,
  "phone": "690000001",
  "description": "Refund",
  "merchant_reference": "refund-1001"
}'
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Bearer sk_test_YOUR_KEY",
    "Idempotency-Key": "refund-1001-attempt-1",
}
payload = {
    "amount": 1000,
    "phone": "690000001",
    "description": "Refund",
    "merchant_reference": "refund-1001",
}

response = requests.post(f"{BASE}/v1/payouts", json=payload, headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/v1/payouts`, {
  method: "POST",
  headers: {
    "Authorization": "Bearer sk_test_YOUR_KEY",
    "Idempotency-Key": "refund-1001-attempt-1",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "amount": 1000,
    "phone": "690000001",
    "description": "Refund",
    "merchant_reference": "refund-1001"
  }),
});
console.log(response.status, await response.json());
```

## Responses

### 201 Created

```json
{
  "id": "pay_3c2b1a0f9e8d7c6b5a49",
  "object": "payout",
  "mode": "test",
  "status": "succeeded",
  "amount": 1000,
  "fee": 25,
  "currency": "XAF",
  "phone_number": "237690000001",
  "operator": "ORANGE",
  "description": "Order 1001",
  "merchant_reference": "order-1001",
  "failure_code": null,
  "failure_message": null,
  "metadata": {},
  "checkout_session": null,
  "created_at": "2026-10-18T09:15:02.123456+00:00",
  "completed_at": "2026-10-18T09:15:02.456789+00:00"
}
```

### 402 Not enough balance

```json
{
  "error": {
    "code": "insufficient_funds",
    "message": "Available balance is 0 XAF, 1025 XAF needed (amount + fee)."
  }
}
```
