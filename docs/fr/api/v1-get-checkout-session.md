# Lire une session de paiement

`GET /v1/checkout-sessions/{id}`

Lire une session de paiement.

`status` vaut `open`, `paid` ou `expired`.

**Authentification:** `Authorization: Bearer sk_test_...` ou `sk_live_...` (clé API secrète).

## Paramètres

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | string (path) | oui | L'`id` de la session (`cs_...`). |

## Exemples

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

## Réponses

### 200 Succès

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
