# Créer une session de paiement

`POST /v1/checkout-sessions`

Créez un lien vers la page de paiement hébergée (version clé API).

Comme le lien de paiement de l'API Apps, avec une durée de vie réglable.

**Authentification:** `Authorization: Bearer sk_test_...` ou `sk_live_...` (clé API secrète).

## Paramètres

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `amount` | integer | oui | Nombre entier de XAF, au moins 10. |
| `description` | string | non | Affichée sur la page de paiement. |
| `merchant_reference` | string | non | **Votre** référence. |
| `redirect_url` | string | non | Où envoyer le client après le paiement. `https` et publique en mode réel. |
| `expires_in_minutes` | integer | non | 1 à 1440, 60 par défaut. |
| `metadata` | object | non | Vos propres données. |

## Exemples

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

## Réponses

### 201 Créée

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

Envoyez `url` à votre client. Les heures sont en UTC ; utilisez `expires_in_seconds` pour les comptes à rebours.
