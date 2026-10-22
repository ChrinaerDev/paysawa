# Obtenir un jeton

`POST /api/token/`

Échangez le nom d'utilisateur et le mot de passe de votre application contre un jeton d'accès.

Appelez ceci en premier. Le jeton est valable `expires_in` secondes (une heure) ; réutilisez-le et demandez-en un nouveau quand un appel répond `401`.
Envoyez-le ensuite sous la forme `Authorization: Token <jeton>`.

**Authentification:** Aucune.

## Paramètres

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `username` | string | oui | Le nom d'utilisateur de l'application, par exemple `pa_1a2b3c4d5e6f7a8b`. |
| `password` | string | oui | Le mot de passe de l'application. |

## Exemples

### cURL

```bash
curl -X POST "https://paysawa.onrender.com/api/token/" \
  -H "Content-Type: application/json" \
  -d '{
  "username": "pa_1a2b3c4d5e6f7a8b",
  "password": "YOUR_APP_PASSWORD"
}'
```

### Python SDK

```python
# The SDK gets and renews tokens for you.
from paysawa import Client

client = Client.from_env()
print(client.get_balance())
```

### Python (requests)

```python
import requests

BASE = "https://paysawa.onrender.com"
payload = {
    "username": "pa_1a2b3c4d5e6f7a8b",
    "password": "YOUR_APP_PASSWORD",
}

response = requests.post(f"{BASE}/api/token/", json=payload)
print(response.status_code, response.json())
```

### JavaScript

```javascript
const BASE = "https://paysawa.onrender.com";

const response = await fetch(`${BASE}/api/token/`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "username": "pa_1a2b3c4d5e6f7a8b",
    "password": "YOUR_APP_PASSWORD"
  }),
});
console.log(response.status, await response.json());
```

## Réponses

### 200 Succès

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 3600
}
```

### 401 Mauvais identifiants

```json
{
  "message": "Invalid app username or password.",
  "code": "invalid_credentials"
}
```

### 429 Trop de tentatives

```json
{
  "message": "Too many requests, slow down.",
  "code": "rate_limited"
}
```

## Notes

Les demandes de jeton sont limitées à 20 par 5 minutes par nom d'utilisateur et par adresse.
