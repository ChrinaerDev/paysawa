# Créer une collecte

`POST /v1/collections`

Demandez à un client de vous payer (version clé API).

Même opération que `collect` dans l'API Apps, avec des objets JSON, un en-tête `Idempotency-Key` et des métadonnées. Le mode (test ou réel) vient de la clé.

**Authentification:** `Authorization: Bearer sk_test_...` ou `sk_live_...` (clé API secrète).

## En-têtes

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `Idempotency-Key` | string | non | Toute chaîne unique. Renvoyer la même clé retourne la collecte d'origine (`200`) au lieu de débiter deux fois ; la même clé avec d'autres paramètres répond `409`. |

## Paramètres

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `amount` | integer | oui | Nombre entier de XAF, au moins 10. |
| `phone` | string | oui | Le numéro de téléphone du client. |
| `description` | string | non | Jusqu'à 160 caractères. |
| `merchant_reference` | string | non | **Votre** référence, jusqu'à 100 caractères. |
| `metadata` | object | non | Vos propres données, jusqu'à 2000 caractères, renvoyées telles quelles. |

## Exemples

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

## Réponses

### 201 Créée

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

### 409 Conflit d'idempotence

```json
{
  "error": {
    "code": "idempotency_conflict",
    "message": "This Idempotency-Key was already used with different parameters."
  }
}
```

## Notes

`status` vaut `pending`, `succeeded`, `failed` ou `expired`. Les champs `fee` et `amount` sont en XAF.
