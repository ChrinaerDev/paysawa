# Documentation Paysawa

Version 0.1.1. URL de base : `https://paysawa.onrender.com`. Une version navigable se trouve dans `docs_site/index.html`.

English: [../README.md](../README.md)

## Introduction

- [Présentation](overview.md)
- [Démarrage](getting-started.md)
- [Authentification](authentication.md)
- [Test et réel](environments.md)

## API Apps

- [Obtenir un jeton (`POST /api/token/`)](api/token.md)
- [Collecte (encaissement) (`POST /api/collect/`)](api/collect.md)
- [Retrait (versement) (`POST /api/withdraw/`)](api/withdraw.md)
- [Statut d'une transaction (`GET /api/transaction/{reference}/`)](api/transaction.md)
- [Solde (`GET /api/balance/`)](api/balance.md)
- [Lien de paiement (`POST /api/get_payment_link/`)](api/get-payment-link.md)

## API v1

- [Créer une collecte (`POST /v1/collections`)](api/v1-create-collection.md)
- [Lire une collecte (`GET /v1/collections/{id}`)](api/v1-get-collection.md)
- [Créer un retrait (`POST /v1/payouts`)](api/v1-create-payout.md)
- [Lire un retrait (`GET /v1/payouts/{id}`)](api/v1-get-payout.md)
- [Solde (`GET /v1/balance`)](api/v1-balance.md)
- [Lister les transactions (`GET /v1/transactions`)](api/v1-list-transactions.md)
- [Créer une session de paiement (`POST /v1/checkout-sessions`)](api/v1-create-checkout-session.md)
- [Lire une session de paiement (`GET /v1/checkout-sessions/{id}`)](api/v1-get-checkout-session.md)

## Webhooks

- [Webhooks](webhooks.md)

## Liens de paiement

- [Page de paiement hébergée](pay-page.md)

## SDK

- [SDK Python](sdk-python.md)

## Référence

- [Erreurs](errors.md)
- [Passer en réel](going-live.md)
- [FAQ](faq.md)
- [API du tableau de bord](dashboard-api.md)
