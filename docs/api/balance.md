# Balance

`GET /api/balance/`

Your available balance in this app's mode (test or live).

`total_balance` is what you can withdraw. `held_balance` is money reserved for withdrawals still being processed. Paysawa keeps one balance per account, so `mtn_balance` and `orange_balance` are always `null`.

**Authentication:** `Authorization: Token <token>` (token from [Get a token](token.md)).

## Examples

### cURL

```bash
curl "https://paysawa.onrender.com/api/balance/" \
  -H "Authorization: Token YOUR_TOKEN"
```

### Python SDK

```python
from paysawa import Client

client = Client.from_env()

balance = client.get_balance()
print(balance.total_balance, balance.held_balance)
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Token YOUR_TOKEN",
}

response = requests.get(f"{BASE}/api/balance/", headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/balance/`, {
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
  "total_balance": 4875,
  "mtn_balance": null,
  "orange_balance": null,
  "held_balance": 0,
  "currency": "XAF"
}
```
