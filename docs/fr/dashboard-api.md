# API du tableau de bord

Les points d'accès qu'utilise un tableau de bord pour gérer un compte. Authentifiez-vous avec le jeton de `POST /auth/login` ou `POST /auth/signup` :
`Authorization: Bearer <jeton>` (valable 12 heures).

| Méthode et chemin | Rôle |
|---|---|
| `POST /auth/signup` | `{name, email, password}` crée un compte (en mode test) et renvoie `{token, merchant}` |
| `POST /auth/login` | `{email, password}` renvoie `{token, merchant}` |
| `GET /me` | le compte : limites, frais, mode réel activé ou non |
| `GET /me/balance` | soldes test et réel : `{test: {available, held}, live: {available, held}}` |
| `GET /me/transactions?mode=&type=&status=&limit=&offset=` | historique des transactions |
| `POST /me/api-keys` | `{mode, label}` crée une clé secrète |
| `GET /me/api-keys` | liste des clés (`prefix`, `revealable`, `last_used_at`...) |
| `GET /me/api-keys/{id}/secret` | réafficher une clé (sert un bouton afficher/masquer) |
| `DELETE /me/api-keys/{id}` | révoquer une clé |
| `POST /me/apps` | `{name, mode, webhook_url?}` crée une application |
| `GET /me/apps` | liste des applications |
| `GET /me/apps/{id}/credentials` | `{username, password, webhook_key, api_base_url}` |
| `PATCH /me/apps/{id}` | changer `name` ou `webhook_url` (une chaîne vide supprime le webhook) |
| `DELETE /me/apps/{id}` | révoquer une application |
| `POST /me/webhook-endpoints` | `{mode, url, events}` enregistre un point d'accès de webhook API v1 ; renvoie `signing_secret` |
| `GET /me/webhook-endpoints`, `GET /me/webhook-endpoints/{id}/secret`, `DELETE /me/webhook-endpoints/{id}` | lister, afficher le secret de signature, supprimer |
| `GET /me/webhook-deliveries` | livraisons de webhooks récentes et leur résultat |

L'inscription et les tentatives de connexion sont limitées.
