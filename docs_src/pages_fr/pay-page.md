---
id: pay-page
title: Page de paiement hébergée
group: Payment links
order: 1
---
# Page de paiement hébergée

La page de paiement hébergée vous permet de vous faire payer sans construire de page de paiement : vous créez un lien, votre client l'ouvre, saisit son numéro MTN ou Orange,
valide sur son téléphone et revient sur votre site. La page s'adapte aux téléphones, existe en français et en anglais (automatique, avec un bouton) et autorise
**3 tentatives** par lien.

## Créer un lien

API Apps :

```bash
curl -X POST {{BASE_URL}}/api/get_payment_link/ \
  -H "Authorization: Token YOUR_TOKEN" -H "Content-Type: application/json" \
  -d '{"amount": "2000", "currency": "XAF", "description": "Order 1002", "external_reference": "order-1002", "redirect_url": "https://shop.example.com/thanks"}'
```

API v1 (permet aussi de choisir la durée de vie du lien, de 1 à 1440 minutes) :

```bash
curl -X POST {{BASE_URL}}/v1/checkout-sessions \
  -H "Authorization: Bearer sk_test_..." -H "Content-Type: application/json" \
  -d '{"amount": 2000, "description": "Order 1002", "merchant_reference": "order-1002", "redirect_url": "https://shop.example.com/thanks", "expires_in_minutes": 60}'
```

Envoyez le `link` (ou `url`) renvoyé à votre client. Les liens durent 60 minutes sauf si vous choisissez autre chose. Les heures sont en UTC ; utilisez `expires_in_seconds` pour les comptes à rebours.

Après un paiement réussi, la page propose un bouton **Retour** et redirige automatiquement après quelques secondes vers votre `redirect_url`
(`https` et public en mode réel). Votre serveur apprend le paiement par [webhook](#/webhooks) : l'événement porte votre référence
(`external_reference` / `merchant_reference`), rattachez donc la commande à celle-ci, pas à la redirection.

## Vérifier un lien

`GET /api/transaction/{reference}/` avec la référence du lien (`cs_...`) répond `PENDING` (ouvert), `SUCCESSFUL` (payé) ou `FAILED` (expiré) ;
quand il est payé, la réponse contient aussi `payment_reference`, la référence du paiement lui-même. Avec l'API v1, utilisez `GET /v1/checkout-sessions/{id}`.

## Construire votre propre page de paiement

Vous pouvez remplacer la page hébergée par la vôtre. Elle a besoin de trois points d'accès **publics** (sans identifiants, CORS activé), identifiés par l'id du lien :

| Appel | Rôle |
|---|---|
| `GET /gate/sessions/{id}` | nom du marchand, montant, description, `status` (`open`, `paid`, `expired`), `attempts_left`, `expires_in_seconds` et `payment` (la dernière tentative) |
| `POST /gate/sessions/{id}/pay` avec `{"phone": "6XXXXXXXX"}` | lancer le paiement : le client reçoit une demande |
| `GET /gate/sessions/{id}/status` | interroger toutes les 2 à 3 secondes pendant que le client valide |

`payment.status` vaut `pending`, `succeeded` ou `failed` (avec un `failure_message`). Quand `status` devient `paid`, la réponse inclut `redirect_url`.
Erreurs à gérer : `already_paid`, `session_expired`, `too_many_attempts`, `payment_in_progress`, `invalid_phone`, `rate_limited`.
