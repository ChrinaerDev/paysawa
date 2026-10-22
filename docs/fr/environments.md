# Test et réel

## Mode test (bac à sable)

Les applications test et les clés `sk_test_` utilisent un fournisseur de mobile money simulé. Aucun argent réel ne bouge et le résultat dépend du numéro de téléphone :

| Numéro de téléphone | Résultat |
|---|---|
| se termine par `0000` (par exemple `670000000`) | le paiement **échoue** |
| se termine par `9999` (par exemple `670009999`) | le paiement **reste en attente** indéfiniment |
| tout autre (par exemple `670000001`) | le paiement **réussit** immédiatement |

Les retraits suivent la même règle. L'argent de test vit dans son propre solde de test : encaissez d'abord avec un numéro de test pour avoir de quoi retirer.

Formats de numéro valides : `6XXXXXXXX`, `2376XXXXXXXX`, `+237 6XX XX XX XX` (les espaces et le `+` sont ignorés).

## Mode réel (live)

- Le mode réel est **activé par compte** par Paysawa, avec des limites. Par défaut : **50 000 XAF par transaction** et **200 000 XAF par jour**, par type de paiement.
- Une collecte réelle envoie vraiment une demande sur le téléphone du client. Un retrait réel envoie vraiment de l'argent.
- Une collecte réelle commence à `PENDING` et devient `SUCCESSFUL` ou `FAILED` quand le client répond (en général en quelques secondes).
  Paysawa suit le paiement pour vous : utilisez un [webhook](webhooks.md) ou interrogez la transaction.
- Les URL de webhook et de redirection doivent être en **https** en mode réel et être des adresses publiques.

Voir [Passer en réel](going-live.md) pour une liste de contrôle.
