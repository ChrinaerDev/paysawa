# List transactions

`GET /v1/transactions`

Your collections and payouts, newest first.

**Authentication:** `Authorization: Bearer sk_test_...` or `sk_live_...` (secret API key).

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `type` | string (query) | no | `collection` or `payout`. |
| `status` | string (query) | no | `pending`, `succeeded`, `failed` or `expired`. |
| `limit` | integer (query) | no | 1 to 100, default 50. |
| `offset` | integer (query) | no | Default 0. |

## Examples

### cURL

```bash
curl "https://paysawa.onrender.com/v1/transactions?status=succeeded&limit=20" \
  -H "Authorization: Bearer sk_test_YOUR_KEY"
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Bearer sk_test_YOUR_KEY",
}
params = {
    "status": "succeeded",
    "limit": 20,
}

response = requests.get(f"{BASE}/v1/transactions", params=params, headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/v1/transactions?status=succeeded&limit=20`, {
  method: "GET",
  headers: {
    "Authorization": "Bearer sk_test_YOUR_KEY"
  },
});
console.log(response.status, await response.json());
```

## Responses

### 200 Success

```json
{
  "data": [
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
  ],
  "limit": 20,
  "offset": 0
}
```
