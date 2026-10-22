# Create a collection

`POST /v1/collections`

Ask a customer to pay you (API key version).

Same operation as `collect` in the Apps API, with JSON objects, an `Idempotency-Key` header and metadata. The mode (test or live) comes from the key.

**Authentication:** `Authorization: Bearer sk_test_...` or `sk_live_...` (secret API key).

## Headers

| Name | Type | Required | Description |
|---|---|---|---|
| `Idempotency-Key` | string | no | Any unique string. Sending the same key again returns the original collection (`200`) instead of charging twice; the same key with other parameters answers `409`. |

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `amount` | integer | yes | Whole XAF, at least 10. |
| `phone` | string | yes | The customer's phone number. |
| `description` | string | no | Up to 160 characters. |
| `merchant_reference` | string | no | **Your** reference, up to 100 characters. |
| `metadata` | object | no | Your own data, up to 2000 characters, returned unchanged. |

## Examples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/v1/collections" \
  -H "Authorization: Bearer sk_test_YOUR_KEY" \
  -H "Idempotency-Key: order-1001-attempt-1" \
  -H "Content-Type: application/json" \
  -d '{
  "amount": 5000,
  "phone": "670000001",
  "description": "Order 1001",
  "merchant_reference": "order-1001"
}'
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Bearer sk_test_YOUR_KEY",
    "Idempotency-Key": "order-1001-attempt-1",
}
payload = {
    "amount": 5000,
    "phone": "670000001",
    "description": "Order 1001",
    "merchant_reference": "order-1001",
}

response = requests.post(f"{BASE}/v1/collections", json=payload, headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/v1/collections`, {
  method: "POST",
  headers: {
    "Authorization": "Bearer sk_test_YOUR_KEY",
    "Idempotency-Key": "order-1001-attempt-1",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "amount": 5000,
    "phone": "670000001",
    "description": "Order 1001",
    "merchant_reference": "order-1001"
  }),
});
console.log(response.status, await response.json());
```

## Responses

### 201 Created

```json
{
  "id": "col_8f3a1c2d4e5f6a7b8c9d",
  "object": "collection",
  "mode": "test",
  "status": "succeeded",
  "amount": 5000,
  "fee": 125,
  "currency": "XAF",
  "phone_number": "237670000001",
  "operator": "MTN",
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

### 409 Idempotency conflict

```json
{
  "error": {
    "code": "idempotency_conflict",
    "message": "This Idempotency-Key was already used with different parameters."
  }
}
```

## Notes

`status` is `pending`, `succeeded`, `failed` or `expired`. Fields `fee` and `amount` are in XAF.
