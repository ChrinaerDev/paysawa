"""Local settings (~/.paysawa/cli.json): server URL, login token, and your test checklist progress.
No API keys are stored: the CLI fetches them from the server when needed."""
import json
import os
from pathlib import Path

DIR = Path.home() / ".paysawa"
FILE = DIR / "cli.json"

# (flag, title, how to do it)
CHECKLIST = [
    ("key_viewed", "Look at your API key", "Menu 4 (Keys): type the key's number to show it, again to hide it."),
    ("deposit_ok", "Make a test deposit", "Menu 1. Use 670000001 (any number ending in anything but 0000/9999 succeeds)."),
    ("deposit_failed", "See a failed deposit", "Menu 1 with a number ending in 0000."),
    ("idempotency", "Replay a request safely (idempotency)", "Menu 7 (Sandbox lab) > scenario 4."),
    ("payout_ok", "Withdraw money to a phone", "Menu 2. Try an Orange number (69...) and an MTN number (67...)."),
    ("payout_refused", "Try withdrawing more than you own", "Menu 7 > scenario 7, or menu 2 with a huge amount."),
    ("payout_refund", "Watch a failed withdrawal refund itself", "Menu 7 > scenario 6 (number ending 0000)."),
    ("webhook_received", "Receive a webhook", "Menu 5 (Webhooks) > Listen. Press d to trigger a deposit."),
    ("session_paid", "Pay a checkout session as a customer", "Menu 6 (Checkout sessions): create one, then 'be the customer'."),
    ("pay_page", "Pay on the real hosted pay page", "Menu 6 > 1: say yes to open the page, pay with 670000001 in the browser; the CLI watches and ticks this off."),
    ("app_created", "Create an app (Campay-style credentials)", "Menu a: n = new app, then look at its username, password and webhook key."),
    ("live_viewed", "Check live-mode readiness", "Menu 8: switch mode (nothing is charged by looking)."),
]


def load() -> dict:
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}


def save(cfg: dict) -> None:
    try:
        DIR.mkdir(exist_ok=True)
        FILE.write_text(json.dumps(cfg, indent=2))
        os.chmod(FILE, 0o600)
    except OSError:
        pass


def done(cfg: dict, email: str) -> set[str]:
    return set(cfg.get("progress", {}).get(email, []))


def mark(cfg: dict, email: str | None, flag: str) -> None:
    if not email:
        return
    flags = cfg.setdefault("progress", {}).setdefault(email, [])
    if flag not in flags:
        flags.append(flag)
        save(cfg)


def next_item(cfg: dict, email: str):
    finished = done(cfg, email)
    for item in CHECKLIST:
        if item[0] not in finished:
            return item
    return None
