# Retrait (versement)

`POST /api/withdraw/`

Envoyez de l'argent de votre solde Paysawa vers n'importe quel numéro MTN ou Orange.

Prélève **montant + frais de Paysawa** sur votre solde disponible. L'argent est retenu pendant que l'opérateur traite le versement et rendu à votre solde s'il échoue.

**Authentification:** `Authorization: Token <jeton>` (jeton obtenu avec [Obtenir un jeton](token.md)).

## Paramètres

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `amount` | string or number | oui | Nombre entier de XAF, au moins 10. |
| `currency` | string | non | Seulement `XAF` (par défaut). |
| `to` | string | oui | Le numéro de téléphone du destinataire. |
| `description` | string | non | Affichée dans votre historique. |
| `external_reference` | string | non | **Votre** référence. Renvoyée dans les statuts et les webhooks. |

## Exemples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/api/withdraw/" \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "amount": "1000",
  "currency": "XAF",
  "to": "690000001",
  "description": "Refund",
  "external_reference": "refund-1001"
}'
```

### Python SDK

```python
from paysawa import Client

client = Client.from_env()

from paysawa import InsufficientFundsError

try:
    tx = client.withdraw(amount=1000, phone="690000001", description="Refund", external_reference="refund-1001")
except InsufficientFundsError:
    print("Not enough balance")
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Token YOUR_TOKEN",
}
payload = {
    "amount": "1000",
    "currency": "XAF",
    "to": "690000001",
    "description": "Refund",
    "external_reference": "refund-1001",
}

response = requests.post(f"{BASE}/api/withdraw/", json=payload, headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/withdraw/`, {
  method: "POST",
  headers: {
    "Authorization": "Token YOUR_TOKEN",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "amount": "1000",
    "currency": "XAF",
    "to": "690000001",
    "description": "Refund",
    "external_reference": "refund-1001"
  }),
});
console.log(response.status, await response.json());
```

## Réponses

### 200 Retrait créé

```json
{
  "reference": "pay_3c2b1a0f9e8d7c6b5a49",
  "status": "SUCCESSFUL",
  "amount": 1000,
  "currency": "XAF",
  "operator": "ORANGE"
}
```

### 402 Solde insuffisant

```json
{
  "message": "Available balance is 0 XAF, 1025 XAF needed (amount + fee).",
  "code": "insufficient_funds"
}
```

## Notes

Un retrait réel peut répondre `PENDING` ; suivez-le comme une collecte. Si la requête elle-même échoue avec une erreur réseau, ne réessayez pas aveuglément : vérifiez d'abord avec `external_reference`.
