# Lien de paiement

`POST /api/get_payment_link/`

Créez un lien vers la page de paiement hébergée pour un montant.

Envoyez le `link` à votre client. Il saisit son numéro sur la page de paiement Paysawa et valide sur son téléphone. Le lien est valable 60 minutes et autorise 3 tentatives. Le webhook de votre application est appelé quand le paiement se termine.

**Authentification:** `Authorization: Token <jeton>` (jeton obtenu avec [Obtenir un jeton](token.md)).

## Paramètres

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `amount` | string or number | oui | Nombre entier de XAF, au moins 10. |
| `currency` | string | non | Seulement `XAF` (par défaut). |
| `description` | string | non | Affichée sur la page de paiement. |
| `external_reference` | string | non | **Votre** référence. Renvoyée dans le webhook. |
| `redirect_url` | string | non | Où envoyer le client après un paiement réussi. `https` et publique en mode réel. |
| `from` | string | non | Accepté et ignoré pour le moment. |
| `failure_redirect_url` | string | non | Accepté et ignoré pour le moment. |

## Exemples

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

## Réponses

### 200 Lien créé

```json
{
  "link": "https://YOUR-PAYSAWA-URL/pay/cs_5d4c3b2a1f0e9d8c7b6a",
  "reference": "cs_5d4c3b2a1f0e9d8c7b6a"
}
```

### 422 URL de redirection refusée

```json
{
  "message": "https is required in live mode",
  "code": "invalid_redirect_url"
}
```

## Notes

Ne considérez pas le retour du client sur votre `redirect_url` comme une preuve de paiement : utilisez le webhook ou le statut de la transaction.
