# Create a checkout session

`POST /v1/checkout-sessions`

Create a payment link to the hosted pay page (API key version).

Like the Apps API payment link, with a configurable lifetime.

**Authentication:** `Authorization: Bearer sk_test_...` or `sk_live_...` (secret API key).

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `amount` | integer | yes | Whole XAF, at least 10. |
| `description` | string | no | Shown on the pay page. |
| `merchant_reference` | string | no | **Your** reference. |
| `redirect_url` | string | no | Where to send the customer after payment. `https` and public in live mode. |
| `expires_in_minutes` | integer | no | 1 to 1440, default 60. |
| `metadata` | object | no | Your own data. |

## Examples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/v1/checkout-sessions" \
  -H "Authorization: Bearer sk_test_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "amount": 2000,
  "description": "Order 1002",
  "merchant_reference": "order-1002",
  "redirect_url": "https://shop.example.com/thanks",
  "expires_in_minutes": 60
}'
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Bearer sk_test_YOUR_KEY",
}
payload = {
    "amount": 2000,
    "description": "Order 1002",
    "merchant_reference": "order-1002",
    "redirect_url": "https://shop.example.com/thanks",
    "expires_in_minutes": 60,
}

response = requests.post(f"{BASE}/v1/checkout-sessions", json=payload, headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/v1/checkout-sessions`, {
  method: "POST",
  headers: {
    "Authorization": "Bearer sk_test_YOUR_KEY",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "amount": 2000,
    "description": "Order 1002",
    "merchant_reference": "order-1002",
    "redirect_url": "https://shop.example.com/thanks",
    "expires_in_minutes": 60
  }),
});
console.log(response.status, await response.json());
```

## Responses

### 201 Created

```json
{
  "id": "cs_5d4c3b2a1f0e9d8c7b6a",
  "object": "checkout_session",
  "mode": "test",
  "status": "open",
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
  "paid_at": null
}
```

## Notes

Send `url` to your customer. Times are UTC; use `expires_in_seconds` for countdowns.
