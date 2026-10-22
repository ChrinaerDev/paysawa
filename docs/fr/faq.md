# FAQ

**Qu'est-ce qu'une application ?** Une application représente l'une de vos applications (une boutique, un backend mobile...). Elle a son propre nom d'utilisateur, mot de passe, clé webhook et mode (test ou réel), et vous pouvez la révoquer sans toucher à vos autres applications.

**Quels opérateurs fonctionnent ?** MTN Mobile Money et Orange Money, pour des numéros camerounais, en XAF.

**Où revoir le mot de passe et la clé webhook de mon application ?** À tout moment : `GET /me/apps/{id}/credentials`, affichés derrière un bouton afficher/masquer dans un tableau de bord.

**Pourquoi ma collecte reste-t-elle `PENDING` ?** Le client n'a pas encore validé. En mode réel c'est normal pendant quelques secondes. En mode test, un numéro se terminant par `9999` reste en attente volontairement.

**L'argent arrive sur mon téléphone ou dans une banque ?** Les collectes sont créditées sur votre **solde Paysawa**. Utilisez un retrait pour envoyer de l'argent vers un numéro MTN ou Orange.

**Combien coûte un paiement ?** Les frais de Paysawa sont déduits de chaque collecte et ajoutés à chaque retrait (2,5 % par défaut, réglé par compte).

**Puis-je utiliser deux fois le même `external_reference` ?** L'API Apps ne le refuse pas : dédupliquez de votre côté. L'API v1 accepte un en-tête `Idempotency-Key`
pour réessayer sans risque.

**Le webhook n'arrive jamais.** Vérifiez que l'URL est publique et en `https` en mode réel, que votre serveur répond `2xx`, et consultez la transaction avec
`GET /api/transaction/{reference}/`. Paysawa retente les livraisons échouées pendant plusieurs heures.

**Y a-t-il des SDK pour d'autres langages ?** Python aujourd'hui (`pip install paysawa`). Tout langage peut appeler l'API HTTP : les exemples de cette documentation incluent cURL et JavaScript.
