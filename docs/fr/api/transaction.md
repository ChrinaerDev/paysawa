# Statut d'une transaction

`GET /api/transaction/{reference}/`

Obtenez l'état le plus récent d'une collecte, d'un retrait ou d'un lien de paiement.

Utilisez la `reference` renvoyée par `collect`, `withdraw` ou `get_payment_link`. `status` vaut `PENDING`, `SUCCESSFUL` ou `FAILED`.
Pour une référence de lien de paiement (`cs_...`) : `PENDING` veut dire ouvert, `SUCCESSFUL` payé, `FAILED` expiré ; une fois payé, la réponse contient aussi `payment_reference`.

**Authentification:** `Authorization: Token <jeton>` (jeton obtenu avec [Obtenir un jeton](token.md)).

## Paramètres

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `reference` | string (path) | oui | `col_...`, `pay_...` ou `cs_...`. |

## Exemples

### cURL

```bash
curl "https://paysawa.onrender.com/api/transaction/col_8f3a1c2d4e5f6a7b8c9d/" \
  -H "Authorization: Token YOUR_TOKEN"
```

### Python SDK

```python
from paysawa import Client

client = Client.from_env()

tx = client.get_transaction("col_8f3a1c2d4e5f6a7b8c9d")
print(tx.status, tx.is_final)

# or wait until it is final:
tx = client.wait_for_transaction("col_8f3a1c2d4e5f6a7b8c9d", timeout=120)
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Token YOUR_TOKEN",
}

response = requests.get(f"{BASE}/api/transaction/col_8f3a1c2d4e5f6a7b8c9d/", headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/transaction/col_8f3a1c2d4e5f6a7b8c9d/`, {
  method: "GET",
  headers: {
    "Authorization": "Token YOUR_TOKEN"
  },
});
console.log(response.status, await response.json());
```

## Réponses

### 200 Succès

```json
{
  "reference": "col_8f3a1c2d4e5f6a7b8c9d",
  "status": "SUCCESSFUL",
  "amount": 5000,
  "currency": "XAF",
  "operator": "MTN",
  "code": "",
  "operator_reference": "op-123",
  "description": "Order 1001",
  "external_reference": "order-1001",
  "external_user": null
}
```

### 200 Paiement échoué

```json
{
  "reference": "col_1a2b3c4d5e6f7a8b9c0d",
  "status": "FAILED",
  "amount": 3000,
  "currency": "XAF",
  "operator": "MTN",
  "code": "",
  "operator_reference": "",
  "description": "",
  "external_reference": "order-1003",
  "external_user": null,
  "reason": "The payment provider rejected this request."
}
```

### 404 Référence inconnue

```json
{
  "message": "Transaction not found.",
  "code": "not_found"
}
```

## Notes

Paysawa suit les paiements réels auprès de l'opérateur pour vous : cet appel renvoie donc des informations à jour. Interrogez toutes les 2 à 3 secondes au maximum.
