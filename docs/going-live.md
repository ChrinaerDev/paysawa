# Going live

Before you move real money:

1. **Ask for live access.** Live mode is enabled per account, with limits (default 50 000 XAF per transaction, 200 000 XAF per day). Ask for higher limits when you have proven the integration.
2. **Create a live app** (or a `sk_live_` key). Test and live credentials are different; keep them in separate configuration.
3. **Use https webhook and redirect URLs.** Live mode refuses plain `http` and private addresses.
4. **Verify every webhook** and compare the amount with your order before delivering anything.
5. **Make your webhook handler idempotent.** The same event can arrive twice.
6. **Do not trust redirects.** A customer returning to your site is not proof of payment. Check the webhook or `GET /api/transaction/{reference}/`.
7. **Handle `PENDING`.** Live payments wait for the customer. Show a waiting screen, never mark an order paid before `SUCCESSFUL`.
8. **Handle failures.** Tell the customer what happened and let them retry with a new request.
9. **Store `reference` and your own `external_reference`** for every payment so you can reconcile.
10. **Do a small real test first:** collect a small amount from your own phone, then withdraw a small amount to it, and compare your balance.
11. **Keep secrets safe.** Revoke a key or app at once if it leaks; create a new one.
