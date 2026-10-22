# Collecte (encaissement)

`POST /api/collect/`

Demandez à un client de vous payer depuis son compte MTN ou Orange Money.

Le client reçoit une demande sur son téléphone et valide avec son code PIN. L'argent est crédité sur votre solde Paysawa **moins les frais de Paysawa**.

En mode **réel**, la réponse est `PENDING` et le paiement se termine en `SUCCESSFUL` ou `FAILED` quand le client répond : suivez-le avec un webhook ou `GET /api/transaction/{reference}/`. En mode **test**, la réponse est déjà finale (voir Test et réel pour les numéros du bac à sable).

**Authentification:** `Authorization: Token <jeton>` (jeton obtenu avec [Obtenir un jeton](token.md)).

## Paramètres

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `amount` | string or number | oui | Nombre entier de XAF, au moins 10. Exemple : `5000` ou `"5000"`. |
| `currency` | string | non | Seulement `XAF` (par défaut). |
| `from` | string | oui | Le numéro de téléphone du client : `6XXXXXXXX`, `2376XXXXXXXX` ; les espaces et le `+` sont ignorés. |
| `description` | string | non | Affichée dans votre historique. |
| `external_reference` | string | non | **Votre** référence (numéro de commande...). Renvoyée dans les statuts et les webhooks. |

## Exemples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/api/collect/" \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
  "amount": "5000",
  "currency": "XAF",
  "from": "670000001",
  "description": "Order 1001",
  "external_reference": "order-1001"
}'
```

### Python SDK

```python
from paysawa import Client

client = Client.from_env()

tx = client.collect(amount=5000, phone="670000001", description="Order 1001",
                    external_reference="order-1001", wait=True)
print(tx.reference, tx.status)
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Token YOUR_TOKEN",
}
payload = {
    "amount": "5000",
    "currency": "XAF",
    "from": "670000001",
    "description": "Order 1001",
    "external_reference": "order-1001",
}

response = requests.post(f"{BASE}/api/collect/", json=payload, headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/collect/`, {
  method: "POST",
  headers: {
    "Authorization": "Token YOUR_TOKEN",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "amount": "5000",
    "currency": "XAF",
    "from": "670000001",
    "description": "Order 1001",
    "external_reference": "order-1001"
  }),
});
console.log(response.status, await response.json());
```

## Réponses

### 200 Demande créée

```json
{
  "reference": "col_8f3a1c2d4e5f6a7b8c9d",
  "ussd_code": "*126#",
  "operator": "MTN",
  "status": "PENDING"
}
```

### 422 Numéro de téléphone invalide

```json
{
  "message": "expected a Cameroonian mobile number like 6XXXXXXXX or +2376XXXXXXXX",
  "code": "invalid_phone"
}
```

### 403 Mode réel non activé

```json
{
  "message": "Live mode is not enabled for this account yet.",
  "code": "live_not_enabled"
}
```

## Notes

`ussd_code` est ce que le client peut composer pour voir le paiement en attente (`*126#` pour MTN, `#150*50#` pour Orange). L'API Apps n'a pas de clé d'idempotence : si une requête échoue avec une erreur réseau, cherchez le paiement par votre `external_reference` avant de réessayer.
