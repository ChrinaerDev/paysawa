---
id: webhooks
title: Webhooks
group: Webhooks
order: 1
---
# Webhooks

Un webhook, c'est Paysawa qui appelle **votre serveur** quand un paiement se termine, pour que vous n'ayez pas à demander sans cesse. Il en existe deux sortes.

| Sorte | Appartient à | Comment il arrive |
|---|---|---|
| **Webhooks d'application** | Une application (nom d'utilisateur/mot de passe) | Requête `GET` vers l'URL de webhook de l'application, données dans l'adresse, signée avec la clé webhook de l'application |
| **Webhooks API v1** | Un compte à clés API (v1) | `POST` d'un corps JSON vers un point d'accès enregistré, signé avec un secret de signature dans un en-tête |

**Vérifiez toujours la signature**, sinon n'importe qui connaissant votre URL pourrait simuler un paiement.

## Webhooks d'application

Définissez l'URL de webhook de l'application à sa création (`webhook_url`) ou plus tard avec `PATCH /me/apps/{id}`.
Une application ne reçoit que les événements des paiements faits **par cette application**, y compris les paiements faits sur ses liens de paiement.

Paysawa appelle :

```
GET https://your-server.example.com/webhooks/paysawa
    ?status=SUCCESSFUL
    &reference=col_8f3a1c2d4e5f6a7b8c9d
    &amount=5000
    &currency=XAF
    &operator=MTN
    &code=
    &operator_reference=op-123
    &external_reference=order-1001
    &signature=eyJhbGciOiJIUzI1NiIs...
```

| Paramètre | Signification |
|---|---|
| `status` | `SUCCESSFUL`, `FAILED` ou `PENDING` |
| `reference` | la référence Paysawa du paiement (`col_...` ou `pay_...`) |
| `amount`, `currency` | montant en XAF, sous forme de texte |
| `operator` | `MTN` ou `ORANGE` quand il est connu |
| `external_reference` | **votre** référence, telle que vous l'avez envoyée |
| `operator_reference` | la référence propre à l'opérateur quand elle existe |
| `signature` | un JWT (HS256) signé avec la **clé webhook** de l'application sur tous les autres paramètres |

### La vérifier

Avec le SDK :

```python
from paysawa import Client, WebhookVerificationError

client = Client.from_env()

@app.get("/webhooks/paysawa")                      # Flask
def paysawa_webhook():
    try:
        event = client.verify_webhook(request.args.to_dict())
    except WebhookVerificationError:
        return "invalid", 401
    order = find_order(event.external_reference)
    if event.is_successful and event.amount == order.total:
        mark_paid(order)
    return "ok"
```

Sans le SDK, décodez `signature` avec votre clé webhook (HS256), puis vérifiez que chaque champ signé est égal au paramètre reçu :

```python
import jwt

def verify(params: dict, webhook_key: str) -> dict:
    signed = jwt.decode(params["signature"], webhook_key, algorithms=["HS256"])
    clean = {k: v for k, v in params.items() if k != "signature"}
    for key, value in signed.items():
        if key not in ("iat", "exp") and str(clean.get(key, "")) != str(value):
            raise ValueError(f"{key} was tampered with")
    return clean
```

```javascript
// Node.js with the "jsonwebtoken" package
const jwt = require("jsonwebtoken");
function verify(query, webhookKey) {
  const signed = jwt.verify(query.signature, webhookKey, { algorithms: ["HS256"] });
  for (const [k, v] of Object.entries(signed)) {
    if (k !== "iat" && k !== "exp" && String(query[k] ?? "") !== String(v)) throw new Error(k + " was tampered with");
  }
  const { signature, ...clean } = query;
  return clean;
}
```

### Règles de livraison

- Répondez avec n'importe quel statut **2xx** pour confirmer. Tout autre statut (ou aucune réponse en 8 secondes) est retenté : jusqu'à 8 tentatives, la première après environ
  une minute, puis en doublant l'intervalle, sans jamais dépasser 6 heures entre deux tentatives.
- Un webhook peut arriver **plusieurs fois**. Rendez votre traitement idempotent : si la commande est déjà payée, ne faites rien et répondez `200`.
- Ne vous fiez pas au webhook seul. S'il n'arrive jamais, `GET /api/transaction/{reference}/` donne la vérité.
- Les URL de webhook réelles doivent être en `https` et publiques. En mode test, `http` est accepté ; les adresses de réseaux privés sont toujours refusées.

## Webhooks API v1

Enregistrez un point d'accès avec `POST /me/webhook-endpoints` (`{"mode": "live", "url": "https://...", "events": []}`, une liste `events` vide veut dire tous les événements).
Événements : `collection.succeeded`, `collection.failed`, `collection.expired`, `payout.succeeded`, `payout.failed`.

```json
{
  "id": "evt_1f2e3d4c5b6a7988",
  "type": "collection.succeeded",
  "created": "2026-10-18T09:15:02.456789+00:00",
  "data": { "id": "col_8f3a1c2d4e5f6a7b8c9d", "object": "collection", "status": "succeeded", "amount": 5000, "fee": 125, "...": "..." }
}
```

En-têtes : `X-Paysawa-Signature: t=<heure unix>,v1=<hex>`, `X-Paysawa-Event`, `X-Paysawa-Delivery`.
La signature est un HMAC-SHA256 de `"<t>.<corps brut de la requête>"` avec le secret de signature de votre point d'accès. Rejetez-la si `t` date de plus de 5 minutes.

```python
import hmac, hashlib, time

def verify(secret: str, raw_body: bytes, header: str) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(","))
    if abs(time.time() - int(parts["t"])) > 300:
        return False
    expected = hmac.new(secret.encode(), f"{parts['t']}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])
```

Répondez avec n'importe quel 2xx. Les livraisons échouées sont retentées selon le même calendrier et peuvent être consultées avec `GET /me/webhook-deliveries`.
