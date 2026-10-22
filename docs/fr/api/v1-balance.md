# Solde

`GET /v1/balance`

Votre solde dans le mode de la clé.

**Authentification:** `Authorization: Bearer sk_test_...` ou `sk_live_...` (clé API secrète).

## Exemples

### cURL

```bash
curl "https://paysawa.onrender.com/v1/balance" \
  -H "Authorization: Bearer sk_test_YOUR_KEY"
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Bearer sk_test_YOUR_KEY",
}

response = requests.get(f"{BASE}/v1/balance", headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/v1/balance`, {
  method: "GET",
  headers: {
    "Authorization": "Bearer sk_test_YOUR_KEY"
  },
});
console.log(response.status, await response.json());
```

## Réponses

### 200 Succès

```json
{
  "mode": "test",
  "currency": "XAF",
  "available": 4875,
  "held": 0
}
```
