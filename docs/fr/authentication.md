# Authentification

Paysawa a trois types d'identifiants. Utilisez celui qui correspond à l'API que vous appelez.

| Identifiant | Sert pour | Envoyé comme |
|---|---|---|
| Nom d'utilisateur + mot de passe d'application | L'API Apps (`/api/...`) | Vous les échangez contre un jeton, puis envoyez `Authorization: Token <jeton>` |
| Clé API secrète | API v1 (`/v1/...`) | `Authorization: Bearer sk_test_...` ou `sk_live_...` |
| Jeton du tableau de bord | Gérer votre compte (`/me/...`) | `Authorization: Bearer <jeton>` obtenu avec `POST /auth/login` |

## Jetons de l'API Apps

1. `POST https://paysawa.onrender.com/api/token/` avec le `username` et le `password` de votre application.
2. Vous recevez un `token` valable `expires_in` secondes (3600, une heure).
3. Envoyez-le à chaque appel : `Authorization: Token <jeton>` (le mot `Bearer` est accepté aussi).
4. Quand un appel répond `401`, demandez un nouveau jeton et recommencez. Le [SDK](sdk-python.md) fait tout cela pour vous.

Réutilisez un jeton pendant toute sa durée de vie au lieu d'en demander un avant chaque appel. Les demandes de jeton sont limitées à 20 par 5 minutes
par nom d'utilisateur et par adresse.

## Clés API

Créez des clés dans votre tableau de bord (ou avec `POST /me/api-keys`). Une clé commence par `sk_test_` (bac à sable) ou `sk_live_` (argent réel) ; **la clé détermine le
mode**. Vous pouvez réafficher une clé à tout moment. Révoquez une clé si elle fuit : les appels faits avec elle s'arrêtent immédiatement.

## Applications et mode

Une application est créée pour un mode, `test` ou `live`. Test et réel ont des soldes, transactions, clés, applications et webhooks séparés.
Une application réelle ne fonctionne qu'une fois le mode réel activé sur votre compte par Paysawa.
