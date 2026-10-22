# Get a checkout session

`GET /v1/checkout-sessions/{id}`

Read a checkout session.

`status` is `open`, `paid` or `expired`.

**Authentication:** `Authorization: Bearer sk_test_...` or `sk_live_...` (secret API key).

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string (path) | yes | The `id` of the session (`cs_...`). |

## Examples

### cURL

```bash
curl "https://paysawa.onrender.com/v1/checkout-sessions/cs_5d4c3b2a1f0e9d8c7b6a" \
  -H "Authorization: Bearer sk_test_YOUR_KEY"
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Bearer sk_test_YOUR_KEY",
}

response = requests.get(f"{BASE}/v1/checkout-sessions/cs_5d4c3b2a1f0e9d8c7b6a", headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/v1/checkout-sessions/cs_5d4c3b2a1f0e9d8c7b6a`, {
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
  "id": "cs_5d4c3b2a1f0e9d8c7b6a",
  "object": "checkout_session",
  "mode": "test",
  "status": "paid",
  "amount": 2000,
  "currency": "XAF",
  "description": "Order 1002",
  "merchant_reference": "order-1002",
  "redirect_url": "https://shop.example.com/thanks",
  "metadata": {},
  "url": "https://YOUR-PAYSAWA-URL/pay/cs_5d4c3b2a1f0e9d8c7b6a",
  "expires_at": "2026-10-18T10:15:02+00:00",
  "expires_in_seconds": 3600,
  "created_at": "2026-10-18T09:15:02+00:00",
  "paid_at": "2026-10-18T09:20:11+00:00"
}
```
