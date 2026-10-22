# Lire une collecte

`GET /v1/collections/{id}`

Lire une collecte.

Les collectes réelles en attente sont actualisées auprès de l'opérateur quand vous les lisez.

**Authentification:** `Authorization: Bearer sk_test_...` ou `sk_live_...` (clé API secrète).

## Paramètres

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | string (path) | oui | L'`id` de la collecte (`col_...`). |

## Exemples

### cURL

```bash
curl "https://paysawa.onrender.com/v1/collections/col_8f3a1c2d4e5f6a7b8c9d" \
  -H "Authorization: Bearer sk_test_YOUR_KEY"
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Bearer sk_test_YOUR_KEY",
}

response = requests.get(f"{BASE}/v1/collections/col_8f3a1c2d4e5f6a7b8c9d", headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/v1/collections/col_8f3a1c2d4e5f6a7b8c9d`, {
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
