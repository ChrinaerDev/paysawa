---
id: getting-started
title: Démarrage
group: Introduction
order: 2
---
# Démarrage

Ce pas-à-pas utilise le **bac à sable** : rien de réel n'est débité.

## 1. Créer votre compte

```bash
curl -X POST {{BASE_URL}}/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name": "Ada Labs", "email": "ada@example.com", "password": "a-long-password"}'
```

La réponse contient un `token` pour l'API du tableau de bord. Gardez-le pour l'étape suivante (il est valable 12 heures ; reconnectez-vous avec `POST /auth/login`).

## 2. Créer une application et obtenir ses identifiants

Une **application** représente votre application chez Paysawa : elle vous donne un **nom d'utilisateur**, un **mot de passe** et une **clé webhook**.

```bash
curl -X POST {{BASE_URL}}/me/apps \
  -H "Authorization: Bearer DASHBOARD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My shop", "mode": "test", "webhook_url": "https://example.com/webhooks/paysawa"}'
```

Vous pouvez relire les identifiants à tout moment (un tableau de bord les affiche derrière un bouton afficher/masquer) :

```bash
curl {{BASE_URL}}/me/apps/APP_ID/credentials -H "Authorization: Bearer DASHBOARD_TOKEN"
```

```json
{
  "username": "pa_1a2b3c4d5e6f7a8b",
  "password": "k3J...43 characters...",
  "webhook_key": "whk_Qe9...",
  "api_base_url": "{{BASE_URL}}/api/"
}
```

> **Gardez le mot de passe et la clé webhook sur votre serveur.** Ne les mettez jamais dans une application mobile, une page web ou un dépôt git.

## 3. Obtenir un jeton d'accès

```bash
curl -X POST {{BASE_URL}}/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "pa_1a2b3c4d5e6f7a8b", "password": "YOUR_APP_PASSWORD"}'
```

```json
{ "token": "eyJhbGciOi...", "expires_in": 3600 }
```

## 4. Encaisser votre premier paiement

```bash
curl -X POST {{BASE_URL}}/api/collect/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": "5000", "currency": "XAF", "from": "670000001", "description": "Order 1001", "external_reference": "order-1001"}'
```

```json
{ "reference": "col_8f3a1c2d4e5f6a7b8c9d", "ussd_code": "*126#", "operator": "MTN", "status": "SUCCESSFUL" }
```

Dans le bac à sable, le résultat est immédiat. Avec une application **réelle**, le statut commence à `PENDING` : le client reçoit une demande sur son téléphone et
confirme avec son code PIN. Voir [Test et réel](#/environments) pour les numéros de test.

## 5. Vérifier le résultat

```bash
curl {{BASE_URL}}/api/transaction/col_8f3a1c2d4e5f6a7b8c9d/ -H "Authorization: Token YOUR_TOKEN"
```

Ou laissez Paysawa vous prévenir : définissez une URL de webhook sur votre application et lisez [Webhooks](#/webhooks).

## 6. Envoyer de l'argent

```bash
curl -X POST {{BASE_URL}}/api/withdraw/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": "1000", "currency": "XAF", "to": "690000001", "description": "Refund", "external_reference": "refund-1001"}'
```

## Ou utilisez le SDK

```bash
pip install paysawa
```

```python
from paysawa import Client

client = Client("pa_1a2b3c4d5e6f7a8b", "YOUR_APP_PASSWORD", "whk_...", base_url="{{BASE_URL}}/api/")
tx = client.collect(5000, "670000001", "Order 1001", "order-1001", wait=True)
print(tx.status)
```

Le guide complet du SDK est dans [SDK Python](#/sdk-python).
