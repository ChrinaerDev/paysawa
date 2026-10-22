# Paysawa

Paysawa est une passerelle de paiement pour le **mobile money au Cameroun** (MTN Mobile Money et Orange Money, montants en XAF).
Avec une seule intégration, vous pouvez **encaisser** de l'argent auprès de vos clients, **retirer** (envoyer) de l'argent vers n'importe quel numéro MTN ou Orange,
partager des **liens de paiement** et recevoir des **webhooks** quand quelque chose se passe.

URL de base de l'API : `https://paysawa.onrender.com`

## Trois façons d'intégrer

| Façon | Vous utilisez | Idéal pour |
|---|---|---|
| **API Apps** (`/api`) | Nom d'utilisateur, mot de passe et clé webhook d'une application | Intégrations de serveur à serveur avec authentification par jeton. Fonctionne avec le [SDK Python](sdk-python.md). |
| **API v1** (`/v1`) | Clé API secrète (`sk_test_...` / `sk_live_...`) | Nouvelles intégrations JSON avec clés d'idempotence et objets plus riches. |
| **Page de paiement hébergée** | Un lien de paiement | Se faire payer sans construire de page de paiement. |

Les trois façons déplacent l'argent du même compte et apparaissent dans le même historique de transactions.

## Concepts essentiels

- **Test et réel.** Une application ou une clé *test* utilise le bac à sable : rien de réel n'est débité et les résultats sont immédiats et prévisibles
  (voir [Test et réel](environments.md)). Une application ou une clé *live* (réelle) déplace de l'argent réel.
- **Un seul solde.** Chaque marchand a un seul solde. Les collectes l'augmentent, les retraits le diminuent. Il n'y a pas de séparation par opérateur.
- **Statuts.** L'API Apps renvoie `PENDING`, `SUCCESSFUL` ou `FAILED`. L'API v1 renvoie `pending`, `succeeded`, `failed` ou `expired`.
- **Les montants** sont des nombres entiers de XAF, au minimum 10.
- **Frais.** Une collecte crédite votre solde du montant moins les frais de Paysawa ; un retrait prélève sur votre solde le montant plus les frais.
  Les frais par défaut sont de 2,5 % et peuvent différer selon le compte.
- **Votre propre référence.** Envoyez un `external_reference` (API Apps) ou un `merchant_reference` (v1) avec chaque paiement. Il revient dans les
  statuts et les webhooks pour que vous puissiez rattacher le paiement à votre commande.

## Par où commencer

1. [Démarrage](getting-started.md) : de zéro à un premier paiement en cinq minutes.
2. [Authentification](authentication.md) : comment fonctionnent les jetons et les clés.
3. [Webhooks](webhooks.md) : comment Paysawa prévient votre serveur qu'un paiement est terminé.
4. [SDK Python](sdk-python.md) : `pip install paysawa`.
