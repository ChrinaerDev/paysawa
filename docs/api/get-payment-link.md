# Payment link

`POST /api/get_payment_link/`

Create a link to the hosted pay page for one amount.

Send the `link` to your customer. They enter their phone number on the Paysawa pay page and approve on their phone. The link is valid for 60 minutes and allows 3 attempts. Your app's webhook is called when the payment finishes.

**Authentication:** `Authorization: Token <token>` (token from [Get a token](token.md)).

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `amount` | string or number | yes | Whole XAF, at least 10. |
| `currency` | string | no | Only `XAF` (default). |
| `description` | string | no | Shown on the pay page. |
| `external_reference` | string | no | **Your** reference. Returned in the webhook. |
| `redirect_url` | string | no | Where to send the customer after a successful payment. `https` and public in live mode. |
| `from` | string | no | Accepted and ignored for now. |
| `failure_redirect_url` | string | no | Accepted and ignored for now. |

## Examples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/api/get_payment_link/" \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "amount": "2000",
  "currency": "XAF",
  "description": "Order 1002",
  "external_reference": "order-1002",
  "redirect_url": "https://shop.example.com/thanks"
}'
```

### Python SDK

```python
from paysawa import Client

client = Client.from_env()

link = client.get_payment_link(amount=2000, description="Order 1002",
                               external_reference="order-1002",
                               redirect_url="https://shop.example.com/thanks")
print(link.link)
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Token YOUR_TOKEN",
}
payload = {
    "amount": "2000",
    "currency": "XAF",
    "description": "Order 1002",
    "external_reference": "order-1002",
    "redirect_url": "https://shop.example.com/thanks",
}

response = requests.post(f"{BASE}/api/get_payment_link/", json=payload, headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/get_payment_link/`, {
  method: "POST",
  headers: {
    "Authorization": "Token YOUR_TOKEN",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "amount": "2000",
    "currency": "XAF",
    "description": "Order 1002",
    "external_reference": "order-1002",
    "redirect_url": "https://shop.example.com/thanks"
  }),
});
console.log(response.status, await response.json());
```

## Responses

### 200 Link created

```json
{
  "link": "https://YOUR-PAYSAWA-URL/pay/cs_5d4c3b2a1f0e9d8c7b6a",
  "reference": "cs_5d4c3b2a1f0e9d8c7b6a"
}
```

### 422 Redirect URL refused

```json
{
  "message": "https is required in live mode",
  "code": "invalid_redirect_url"
}
```

## Notes

Do not trust the customer's return to your `redirect_url` as proof of payment: use the webhook or the transaction status.
