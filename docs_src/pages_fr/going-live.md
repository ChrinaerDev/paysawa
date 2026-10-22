---
id: going-live
title: Passer en réel
group: Reference
order: 2
---
# Passer en réel

Avant de déplacer de l'argent réel :

1. **Demandez l'accès au mode réel.** Il est activé par compte, avec des limites (par défaut 50 000 XAF par transaction, 200 000 XAF par jour). Demandez des limites plus hautes quand l'intégration a fait ses preuves.
2. **Créez une application réelle** (ou une clé `sk_live_`). Les identifiants de test et de réel sont différents ; gardez-les dans des configurations séparées.
3. **Utilisez des URL de webhook et de redirection en https.** Le mode réel refuse `http` simple et les adresses privées.
4. **Vérifiez chaque webhook** et comparez le montant à votre commande avant de livrer quoi que ce soit.
5. **Rendez votre traitement de webhook idempotent.** Le même événement peut arriver deux fois.
6. **Ne vous fiez pas aux redirections.** Un client qui revient sur votre site n'est pas une preuve de paiement. Vérifiez le webhook ou `GET /api/transaction/{reference}/`.
7. **Gérez `PENDING`.** Les paiements réels attendent le client. Affichez un écran d'attente, ne marquez jamais une commande payée avant `SUCCESSFUL`.
8. **Gérez les échecs.** Dites au client ce qui s'est passé et laissez-le réessayer avec une nouvelle demande.
9. **Conservez la `reference` et votre propre `external_reference`** de chaque paiement pour pouvoir rapprocher les comptes.
10. **Faites d'abord un petit test réel :** encaissez un petit montant depuis votre propre téléphone, puis retirez un petit montant vers lui, et comparez votre solde.
11. **Protégez vos secrets.** Révoquez une clé ou une application dès qu'elle fuit ; créez-en une nouvelle.
