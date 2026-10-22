---
id: environments
title: Test and live
group: Introduction
order: 4
---
# Test and live

## Test mode (sandbox)

Test apps and `sk_test_` keys use a simulated mobile money provider. No real money moves, and results are decided by the phone number:

| Phone number | Result |
|---|---|
| ends with `0000` (for example `670000000`) | the payment **fails** |
| ends with `9999` (for example `670009999`) | the payment **stays pending** forever |
| anything else (for example `670000001`) | the payment **succeeds** instantly |

Withdrawals follow the same rule. Test money lives in its own test balance: collect with a sandbox number first to have something to withdraw.

Valid phone formats: `6XXXXXXXX`, `2376XXXXXXXX`, `+237 6XX XX XX XX` (spaces and `+` are ignored).

## Live mode

- Live is **enabled per account** by Paysawa, with limits. The defaults are **50 000 XAF per transaction** and **200 000 XAF per day**, per type of payment.
- A live collection really sends a prompt to the customer's phone. A live withdrawal really sends money.
- A live collection starts as `PENDING` and becomes `SUCCESSFUL` or `FAILED` when the customer answers (usually within seconds).
  Paysawa follows the payment for you, so use a [webhook](#/webhooks) or poll the transaction.
- Webhook URLs and redirect URLs must be **https** in live mode and must be public addresses.

See [Going live](#/going-live) for a checklist.
