# Solde

`GET /api/balance/`

Votre solde disponible dans le mode de cette application (test ou réel).

`total_balance` est ce que vous pouvez retirer. `held_balance` est l'argent réservé pour des retraits en cours de traitement. Paysawa tient un seul solde par compte : `mtn_balance` et `orange_balance` valent donc toujours `null`.

**Authentification:** `Authorization: Token <jeton>` (jeton obtenu avec [Obtenir un jeton](token.md)).

## Exemples

### cURL

```bash
curl "https://paysawa.onrender.com/api/balance/" \
  -H "Authorization: Token YOUR_TOKEN"
```

### Python SDK

```python
from paysawa import Client

client = Client.from_env()

balance = client.get_balance()
print(balance.total_balance, balance.held_balance)
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
headers = {
    "Authorization": "Token YOUR_TOKEN",
}

response = requests.get(f"{BASE}/api/balance/", headers=headers)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/balance/`, {
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
  "total_balance": 4875,
  "mtn_balance": null,
  "orange_balance": null,
  "held_balance": 0,
  "currency": "XAF"
}
```
