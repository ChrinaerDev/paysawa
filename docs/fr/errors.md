# Erreurs

## Forme

L'API Apps (`/api`) répond aux erreurs ainsi :

```json
{ "message": "Available balance is 0 XAF, 1025 XAF needed (amount + fee).", "code": "insufficient_funds" }
```

L'API v1 et l'API du tableau de bord enveloppent les mêmes deux champs :

```json
{ "error": { "code": "insufficient_funds", "message": "Available balance is 0 XAF, 1025 XAF needed (amount + fee)." } }
```

Utilisez le statut HTTP pour savoir *quel genre* de problème c'est et `code` pour décider *quoi faire*. `message` est destiné aux humains (il est en anglais).

## Codes

| HTTP | `code` | Signification |
|---|---|---|
| 400 | `invalid_amount` | le montant n'est pas un nombre entier positif de XAF |
| 400 | `invalid_currency` | seul `XAF` est accepté |
| 401 | `unauthorized` | jeton / clé manquant, invalide ou expiré |
| 401 | `invalid_credentials` | mauvais nom d'utilisateur ou mot de passe d'application |
| 402 | `insufficient_funds` | un retrait demande plus que votre solde disponible (montant + frais) |
| 403 | `live_not_enabled` | le mode réel n'est pas encore activé pour votre compte |
| 403 | `account_suspended` | votre compte ne peut pas effectuer de paiements |
| 404 | `not_found` | référence ou id inconnu |
| 409 | `idempotency_conflict` | le même `Idempotency-Key` a été utilisé avec d'autres paramètres (v1) |
| 409 | `payment_in_progress` | un paiement sur ce lien attend déjà le client |
| 409 | `already_paid` | le lien est déjà payé |
| 410 | `session_expired` | le lien de paiement a expiré |
| 422 | `invalid_phone` | ce n'est pas un numéro mobile camerounais |
| 422 | `amount_too_small` | en dessous du minimum de 10 XAF |
| 422 | `amount_too_large` | au-dessus de votre limite par transaction |
| 422 | `daily_limit_exceeded` | au-dessus de votre limite journalière |
| 422 | `invalid_request` | un champ obligatoire manque ou est mal formé |
| 422 | `invalid_redirect_url` / `invalid_url` | URL de redirection ou de webhook refusée (publique, https en mode réel) |
| 429 | `rate_limited` / `too_many_attempts` | ralentissez |
| 503 | `provider_unavailable` | côté opérateur mobile money indisponible, réessayez bientôt |
| 503 | `busy` / `db_timeout` | Paysawa est occupé : réessayez les lectures ; pour un paiement, vérifiez-le avant de réessayer |
| 500 | `internal_error` | problème inattendu de notre côté |

## Paiements qui échouent plus tard

Une requête peut réussir (`200`) et le paiement finir quand même en `FAILED` : le client a refusé, n'avait pas assez d'argent ou n'a rien fait. Le champ `reason`
de la transaction l'explique. Un **retrait** échoué rend automatiquement l'argent retenu à votre solde.

## Si une requête de paiement échoue avec une erreur réseau ou un 5xx

Ne la renvoyez pas aveuglément : vous risquez de débiter le client deux fois. Cherchez d'abord le paiement avec l'`external_reference` que vous avez envoyé
(gardez votre propre enregistrement), et ne réessayez que s'il n'existe pas.
