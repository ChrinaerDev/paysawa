---
id: faq
title: FAQ
group: Reference
order: 3
---
# FAQ

**What is an app?** An app represents one application of yours (a shop, a mobile backend...). It has its own username, password, webhook key and mode (test or live), and you can revoke it without touching your other apps.

**Which operators work?** MTN Mobile Money and Orange Money, for Cameroonian numbers, in XAF.

**Where do I see my app password and webhook key again?** Any time: `GET /me/apps/{id}/credentials`, shown behind a show/hide toggle in a dashboard.

**Why is my collection still `PENDING`?** The customer has not approved yet. In live mode this is normal for a few seconds. In test mode a number ending in `9999` stays pending on purpose.

**Do I get my money in my phone or in a bank?** Collections are credited to your **Paysawa balance**. Use a withdrawal to send money to an MTN or Orange number.

**What does a payment cost?** Paysawa's fee is deducted from each collection and added to each withdrawal (default 2.5%, set per account).

**Can I charge the same `external_reference` twice?** The Apps API does not reject it: deduplicate on your side. API v1 supports an `Idempotency-Key` header
for safe retries.

**The webhook never arrives.** Check that the URL is public and `https` in live mode, that your server answers `2xx`, and look at the transaction with
`GET /api/transaction/{reference}/`. Paysawa retries failed deliveries for several hours.

**Are there SDKs for other languages?** Python today (`pip install paysawa`). Any language can call the HTTP API: the examples in this documentation include cURL and JavaScript.
