# Créer un retrait

`POST /v1/payouts`

Envoyez de l'argent de votre solde vers un téléphone (version clé API).

Prélève montant + frais sur votre solde disponible (retenu d'abord, rendu s'il échoue). Accepte l'en-tête `Idempotency-Key` comme les collectes.

**Authentification:** `Authorization: Bearer sk_test_...` ou `sk_live_...` (clé API secrète).

## En-têtes

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `Idempotency-Key` | string | non | Chaîne unique pour réessayer sans risque. |

## Paramètres

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `amount` | integer | oui | Nombre entier de XAF, au moins 10. |
| `phone` | string | oui | Le numéro de téléphone du destinataire. |
| `description` | string | non | Jusqu'à 160 caractères. |
| `merchant_reference` | string | non | **Votre** référence. |
| `metadata` | object | non | Vos propres données. |

## Exemples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/v1/payouts" \
  -H "Authorization: Bearer sk_test_YOUR_KEY" \
  -H "Idempotency-Key: refund-1001-attempt-1" \
  -H "Content-Type: application/json" \
  -d '{
  "amount": 1000,
  "phone": "690000001",
  "description": "Refund",
  "merchant_reference": "refund-1001"
}'
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Bearer sk_test_YOUR_KEY",
    "Idempotency-Key": "refund-1001-attempt-1",
}
payload = {
    "amount": 1000,
    "phone": "690000001",
    "description": "Refund",
    "merchant_reference": "refund-1001",
}

response = requests.post(f"{BASE}/v1/payouts", json=payload, headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/v1/payouts`, {
  method: "POST",
  headers: {
    "Authorization": "Bearer sk_test_YOUR_KEY",
    "Idempotency-Key": "refund-1001-attempt-1",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "amount": 1000,
    "phone": "690000001",
    "description": "Refund",
    "merchant_reference": "refund-1001"
  }),
});
console.log(response.status, await response.json());
```

## Réponses

### 201 Créé

```json
{
  "id": "pay_3c2b1a0f9e8d7c6b5a49",
  "object": "payout",
  "mode": "test",
  "status": "succeeded",
  "amount": 1000,
  "fee": 25,
  "currency": "XAF",
  "phone_number": "237690000001",
  "operator": "ORANGE",
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

### 402 Solde insuffisant

```json
{
  "error": {
    "code": "insufficient_funds",
    "message": "Available balance is 0 XAF, 1025 XAF needed (amount + fee)."
  }
}
```
