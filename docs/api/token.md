# Get a token

`POST /api/token/`

Exchange your app username and password for an access token.

Call this first. The token is valid for `expires_in` seconds (one hour); reuse it, and ask for a new one when a call answers `401`.
Send it afterwards as `Authorization: Token <token>`.

**Authentication:** None.

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `username` | string | yes | The app username, like `pa_1a2b3c4d5e6f7a8b`. |
| `password` | string | yes | The app password. |

## Examples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/api/token/" \
  -H "Content-Type: application/json" \
  -d '{
  "username": "pa_1a2b3c4d5e6f7a8b",
  "password": "YOUR_APP_PASSWORD"
}'
```

### Python SDK

```python
# The SDK gets and renews tokens for you.
from paysawa import Client

client = Client.from_env()
print(client.get_balance())
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
payload = {
    "username": "pa_1a2b3c4d5e6f7a8b",
    "password": "YOUR_APP_PASSWORD",
}

response = requests.post(f"{BASE}/api/token/", json=payload)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/token/`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "username": "pa_1a2b3c4d5e6f7a8b",
    "password": "YOUR_APP_PASSWORD"
  }),
});
console.log(response.status, await response.json());
```

## Responses

### 200 Success

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 3600
}
```

### 401 Wrong credentials

```json
{
  "message": "Invalid app username or password.",
  "code": "invalid_credentials"
}
```

### 429 Too many attempts

```json
{
  "message": "Too many requests, slow down.",
  "code": "rate_limited"
}
```

## Notes

Token requests are limited to 20 per 5 minutes per username and address.
