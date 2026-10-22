---
id: sdk-python
title: SDK Python
group: SDKs
order: 1
---
# SDK Python

```bash
pip install paysawa
```

Nécessite Python 3.9 ou plus récent. Code source et suivi des problèmes : le dépôt `paysawa-python`.

## Créer un client

```python
from paysawa import Client

client = Client(
    app_username="pa_1a2b3c4d5e6f7a8b",
    app_password="YOUR_APP_PASSWORD",
    webhook_key="whk_...",
    base_url="{{BASE_URL}}/api/",     # or set the PAYSAWA_BASE_URL environment variable
)
```

Mieux, gardez les secrets hors du code et lisez-les dans l'environnement :

```bash
export PAYSAWA_APP_USERNAME=pa_1a2b3c4d5e6f7a8b
export PAYSAWA_APP_PASSWORD=...
export PAYSAWA_WEBHOOK_KEY=whk_...
export PAYSAWA_BASE_URL={{BASE_URL}}/api/
```

```python
client = Client.from_env()
```

Le client obtient et renouvelle seul les jetons d'accès. Utilisez `with Client.from_env() as client:` pour fermer les connexions quand vous avez fini.

## Encaisser (collect)

```python
tx = client.collect(amount=5000, phone="670000001", description="Order 1001", external_reference="order-1001")
print(tx.reference, tx.status, tx.operator)        # col_...  PENDING  MTN
```

Ajoutez `wait=True` pour attendre que le paiement soit terminé (`timeout=120` secondes par défaut) :

```python
tx = client.collect(5000, "670000001", "Order 1001", "order-1001", wait=True)
if tx.is_successful:
    ...
```

## Retirer (withdraw)

```python
tx = client.withdraw(amount=1000, phone="690000001", description="Refund", external_reference="refund-1001")
```

Lève `InsufficientFundsError` si le montant plus les frais dépasse votre solde.

## Vérifier un paiement, l'attendre

```python
tx = client.get_transaction("col_8f3a1c2d4e5f6a7b8c9d")
tx = client.wait_for_transaction("col_8f3a1c2d4e5f6a7b8c9d", timeout=120, interval=3)
```

`wait_for_transaction` lève `WaitTimeoutError` (avec `.transaction`, le dernier état) si le paiement est encore en attente quand le temps est écoulé.

Une transaction se comporte comme un dictionnaire et comme un objet : `tx["status"]` et `tx.status` fonctionnent, ainsi que `tx.is_pending`, `tx.is_successful`,
`tx.is_failed` et `tx.is_final`.

## Solde et liens de paiement

```python
balance = client.get_balance()
print(balance.total_balance, balance.held_balance)

link = client.get_payment_link(amount=2000, description="Order 1002",
                               external_reference="order-1002", redirect_url="https://shop.example.com/thanks")
print(link.link)
```

## Webhooks

```python
event = client.verify_webhook(request.args.to_dict())     # raises WebhookVerificationError if the webhook is not authentic
```

Flask utilise `request.args.to_dict()`, FastAPI `dict(request.query_params)`, Django `request.GET.dict()`. Voir [Webhooks](#/webhooks).

## Asynchrone

```python
from paysawa import AsyncClient

async with AsyncClient.from_env() as client:
    tx = await client.collect(5000, "670000001", "Order 1001", "order-1001", wait=True)
```

## Erreurs

Toutes les erreurs héritent de `PaysawaError` (`.message`, `.status`, `.code`) :

| Exception | Quand |
|---|---|
| `AuthenticationError` | mauvais nom d'utilisateur ou mot de passe d'application |
| `PermissionDeniedError` | mode réel non activé, compte suspendu |
| `InvalidRequestError` | montant ou numéro invalide, référence inconnue, limites |
| `InsufficientFundsError` | retrait supérieur au solde (un cas de `InvalidRequestError`) |
| `RateLimitError` | trop de requêtes |
| `ServerError`, `NetworkError` | Paysawa occupé ou injoignable |
| `WaitTimeoutError` | `wait_for_transaction` a abandonné |
| `WebhookVerificationError` | le webhook n'est pas authentique : ignorez-le |

```python
from paysawa import InsufficientFundsError, PaysawaError

try:
    client.withdraw(100000, "690000001")
except InsufficientFundsError:
    ...
except PaysawaError as exc:
    print(exc.status, exc.code, exc.message)
```

**Les paiements ne sont jamais retentés automatiquement**, donc une nouvelle tentative ne peut jamais débiter un client deux fois. Les lectures sont retentées deux fois en cas d'erreur réseau ou de 5xx.

## Mise à jour

```bash
pip install --upgrade paysawa
pip show paysawa          # the installed version
```
