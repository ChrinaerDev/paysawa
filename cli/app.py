"""Paysawa CLI: the whole product in a terminal. Talks to the HTTP API only."""
import hashlib
import hmac
import json
import os
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cli import state, ui
from cli.api import Api, ApiError

STATUS_COLOR = {"succeeded": "green", "paid": "green", "failed": "red", "pending": "yellow", "expired": "dim", "open": "cyan"}


class Ctx:
    def __init__(self, cfg: dict, api: Api):
        self.cfg = cfg
        self.api = api
        self.mode = "test"
        self.email: str | None = None
        self.me: dict | None = None
        self.last_phone = "670000001"
        self.last_session: str | None = None


# ------------------------------------------------------------------ small helpers
def fmt(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def calc_fee(amount: int, bps: int) -> int:  # same rule as the server
    if bps <= 0 or amount <= 1:
        return 0
    return min((amount * bps + 9_999) // 10_000, amount - 1)


def local_time(iso: str | None) -> str:
    """Server times are UTC; show them in the viewer's own timezone to avoid confusion."""
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return iso or "-"


def colored(status: str) -> str:
    color = STATUS_COLOR.get(status, "white")
    return f"[{color}]{status}[/{color}]"


def mark(ctx: Ctx, flag: str) -> None:
    state.mark(ctx.cfg, ctx.email, flag)


def get_me(ctx: Ctx, refresh: bool = False) -> dict:
    if refresh or not ctx.me or "fees_bps" not in ctx.me:
        ctx.me = ctx.api.request("GET", "/me")
    return ctx.me


def ask_phone(ctx: Ctx, label: str = "Phone number") -> str:
    phone = ui.ask(f"{label} (MTN 67x/68x/650-654, Orange 69x/655-659)", default=ctx.last_phone).strip()
    ctx.last_phone = phone
    return phone


def ask_amount(label: str = "Amount in XAF", default: str = "5000") -> int:
    while True:
        raw = ui.ask(label, default=default).replace(" ", "")
        if raw.isdigit() and int(raw) >= 10:
            return int(raw)
        ui.err("Enter a whole number, at least 10.")


def live_guard(summary: str) -> bool:
    ui.panel(f"[bold red]REAL MONEY[/bold red]\n{summary}", title="LIVE mode", style="red")
    return ui.ask("Type LIVE to confirm (anything else cancels)", default="") == "LIVE"


def show_tx(tx: dict) -> None:
    rows = [
        ("id", tx["id"]), ("type", tx["object"]), ("status", colored(tx["status"])),
        ("amount", f"{fmt(tx['amount'])} XAF"), ("fee", f"{fmt(tx['fee'])} XAF"),
        ("phone", tx["phone_number"]), ("operator", tx.get("operator") or "-"),
        ("your ref", tx.get("merchant_reference") or "-"),
    ]
    if tx.get("failure_message"):
        rows.append(("reason", tx["failure_message"]))
    color = STATUS_COLOR.get(tx["status"], "white")
    ui.panel("\n".join(f"{k:<10}{v}" for k, v in rows), title=f"{tx['object']} {tx['status']}", style=color)


def wait_tx(ctx: Ctx, tx: dict, key: str) -> dict:
    if tx["status"] != "pending":
        return tx
    kind = "collections" if tx["object"] == "collection" else "payouts"
    seconds = 6 if ctx.mode == "test" else 120
    message = "Waiting for the customer to approve on their phone..." if kind == "collections" else "Waiting for the operator..."
    deadline = time.time() + seconds
    with ui.spinner(message):
        while time.time() < deadline:
            time.sleep(2)
            tx = ctx.api.request("GET", f"/v1/{kind}/{tx['id']}", auth="key", key=key)
            if tx["status"] != "pending":
                break
    return tx


def key_of(ctx: Ctx) -> str:
    return ctx.api.key_for(ctx.mode)


def call_collect(ctx: Ctx, phone: str, amount: int, idem: str | None = None, desc: str = "CLI deposit") -> dict:
    return ctx.api.request(
        "POST", "/v1/collections", auth="key", key=key_of(ctx),
        headers={"Idempotency-Key": idem or f"cli-{uuid.uuid4().hex[:12]}"},
        json={"amount": amount, "phone": phone, "description": desc},
    )


def call_payout(ctx: Ctx, phone: str, amount: int, desc: str = "CLI withdrawal") -> dict:
    return ctx.api.request(
        "POST", "/v1/payouts", auth="key", key=key_of(ctx),
        headers={"Idempotency-Key": f"cli-{uuid.uuid4().hex[:12]}"},
        json={"amount": amount, "phone": phone, "description": desc},
    )


def my_balance(ctx: Ctx) -> dict:
    return ctx.api.request("GET", "/v1/balance", auth="key", key=key_of(ctx))


# ------------------------------------------------------------------ header and menus
def header(ctx: Ctx) -> None:
    ui.clear()
    online = ctx.api.health()
    lines = [f"Server   {ctx.api.base_url}   " + ("[green]online[/green]" if online else "[red]offline[/red]")]
    if ctx.email:
        badge = "[black on green] TEST [/]" if ctx.mode == "test" else "[white on red] LIVE [/]"
        lines.append(f"Account  {ctx.email}    Mode {badge}")
        try:
            bal = ctx.api.request("GET", "/me/balance")[ctx.mode]
            lines.append(f"Balance  available [bold]{fmt(bal['available'])}[/bold] XAF    held {fmt(bal['held'])} XAF")
        except ApiError as exc:
            if exc.status == 401:
                raise
            lines.append(f"[yellow]balance unavailable: {exc.message}[/yellow]")
    else:
        lines.append("Not logged in")
    ui.panel("\n".join(lines), title="PAYSAWA")
    if ctx.email:
        item = state.next_item(ctx.cfg, ctx.email)
        if item:
            ui.tip(f"[bold]{item[1]}[/bold]\n{item[2]}\n[dim](menu 9 shows the full checklist)[/dim]")
        else:
            ui.tip("You have tried everything on the checklist. Next: a tiny real test in LIVE mode, once the server is deployed.")


def logout(ctx: Ctx, silent: bool = False) -> None:
    ctx.api.token = None
    ctx.api.forget_keys()
    ctx.email = None
    ctx.me = None
    ctx.mode = "test"
    ctx.cfg.pop("token", None)
    ctx.cfg.pop("email", None)
    state.save(ctx.cfg)
    if not silent:
        ui.ok("Logged out.")


def logged_in(ctx: Ctx, data: dict) -> None:
    ctx.api.token = data["token"]
    ctx.api.forget_keys()
    ctx.me = data["merchant"]
    ctx.email = ctx.me["email"]
    ctx.cfg["token"] = data["token"]
    ctx.cfg["email"] = ctx.email
    state.save(ctx.cfg)
    ui.ok(f"Welcome, {ctx.me['name']}.")


def signup(ctx: Ctx) -> None:
    name = ui.ask("Your name or business name")
    email = ui.ask("Email")
    password = ui.ask("Password (min 8 characters)", password=True)
    if ui.ask("Repeat password", password=True) != password:
        ui.err("Passwords do not match.")
        return
    logged_in(ctx, ctx.api.request("POST", "/auth/signup", auth="none", json={"name": name, "email": email, "password": password}))
    ui.say("Your account starts in TEST mode with its own sandbox keys. Nothing real is charged.")
    ui.pause()


def login(ctx: Ctx) -> None:
    email = ui.ask("Email")
    password = ui.ask("Password", password=True)
    logged_in(ctx, ctx.api.request("POST", "/auth/login", auth="none", json={"email": email, "password": password}))


def change_server(ctx: Ctx) -> None:
    url = ui.ask("Server URL", default=ctx.api.base_url).strip().rstrip("/")
    ctx.api.base_url = url
    ctx.cfg["base_url"] = url
    logout(ctx, silent=True)
    ui.ok(f"Server set to {url}. Log in again.")
    ui.pause()


# ------------------------------------------------------------------ money screens
def deposit(ctx: Ctx) -> None:
    hint = ("TEST numbers: 670000001 succeeds, 670000000 fails, 670009999 stays pending."
            if ctx.mode == "test" else "LIVE: a real prompt goes to that phone and real money moves.")
    ui.panel("A deposit means: you ask a phone to pay you. The customer approves with their PIN and the money lands "
             "in your Paysawa balance (minus the fee).\n" + hint, title="Deposit (collect)")
    phone = ask_phone(ctx)
    amount = ask_amount()
    desc = ui.ask("Description", default="CLI deposit")
    if ctx.mode == "live" and not live_guard(f"REQUEST {fmt(amount)} XAF from {phone}"):
        return
    tx = call_collect(ctx, phone, amount, desc=desc)
    tx = wait_tx(ctx, tx, key_of(ctx))
    show_tx(tx)
    if tx["status"] == "succeeded":
        mark(ctx, "deposit_ok")
    elif tx["status"] == "failed":
        mark(ctx, "deposit_failed")
    else:
        ui.warn("Still pending. Check it later in menu 3.")
    ui.pause()


def withdraw(ctx: Ctx) -> None:
    me = get_me(ctx)
    before = my_balance(ctx)
    ui.panel("A withdrawal pays money out of your Paysawa balance to any MTN or Orange number. "
             "Funds are held first and returned if it fails.\n"
             f"Available now: {fmt(before['available'])} XAF   Fee: {me['fees_bps']['payout'] / 100:.2f}%", title="Withdraw (payout)")
    phone = ask_phone(ctx, "Pay to phone number")
    amount = ask_amount(default="1000")
    total = amount + calc_fee(amount, me["fees_bps"]["payout"])
    ui.say(f"You will be debited {fmt(total)} XAF (amount + fee).")
    if total > before["available"]:
        ui.warn("That is more than your available balance.")
        if ctx.mode == "live" or not ui.confirm("Send it anyway to see how Paysawa refuses it?", default=True):
            return
    if ctx.mode == "live" and not live_guard(f"SEND {fmt(amount)} XAF to {phone}"):
        return
    try:
        tx = call_payout(ctx, phone, amount)
    except ApiError as exc:
        if exc.code == "insufficient_funds":
            ui.err(exc.message)
            mark(ctx, "payout_refused")
            ui.pause()
            return
        raise
    tx = wait_tx(ctx, tx, key_of(ctx))
    show_tx(tx)
    if tx["status"] == "succeeded":
        mark(ctx, "payout_ok")
    elif tx["status"] == "failed":
        after = my_balance(ctx)
        if after["available"] == before["available"] and after["held"] == before["held"]:
            ui.ok("The failed withdrawal was refunded: your balance is back to what it was.")
            mark(ctx, "payout_refund")
    else:
        ui.warn("Still pending. The funds stay held until the operator answers. Check menu 3 later.")
    ui.pause()


def balance_screen(ctx: Ctx) -> None:
    bal = ctx.api.request("GET", "/me/balance")
    ui.table("Balances (XAF)", ["Mode", "Available", "Held"],
             [[m, fmt(bal[m]["available"]), fmt(bal[m]["held"])] for m in ("test", "live")])
    txs = ctx.api.request("GET", "/me/transactions", params={"mode": ctx.mode, "limit": 10})["data"]
    if not txs:
        ui.say(f"No {ctx.mode} transactions yet.")
    else:
        ui.table(f"Last transactions ({ctx.mode})", ["#", "Id", "Type", "Status", "Amount", "Fee", "Phone", "When"],
                 [[i, t["id"], t["object"], colored(t["status"]), fmt(t["amount"]), fmt(t["fee"]), t["phone_number"],
                   (t["created_at"] or "")[:19].replace("T", " ")] for i, t in enumerate(txs, 1)])
        pick = ui.ask("Number to inspect (Enter to go back)", default="")
        if pick.isdigit() and 1 <= int(pick) <= len(txs):
            show_tx(txs[int(pick) - 1])
    ui.pause()


# ------------------------------------------------------------------ keys and credentials
def keys_screen(ctx: Ctx) -> None:
    shown_keys: dict[str, str] = {}
    shown_hooks: dict[str, str] = {}
    while True:
        ui.clear()
        keys = ctx.api.request("GET", "/me/api-keys")["data"]
        hooks = ctx.api.request("GET", "/me/webhook-endpoints")["data"]
        me = get_me(ctx)
        rows = []
        for i, k in enumerate(keys, 1):
            if k["revoked_at"]:
                status = "[dim]revoked[/dim]"
            elif k["id"] in shown_keys:
                status = "[green]shown below[/green]"
            elif k["revealable"]:
                status = "hidden  (type the number to show)"
            else:
                status = "[yellow]old key, cannot be shown[/yellow]"
            masked = k["prefix"] + "*" * 16
            rows.append([i, k["mode"], k["label"] or "-", masked, status, (k["last_used_at"] or "never")[:19].replace("T", " ")])
        ui.table("API keys (secret keys, keep them private)", ["#", "Mode", "Label", "Key", "Status", "Last used"], rows)
        for i, k in enumerate(keys, 1):
            if k["id"] in shown_keys:
                ui.raw(f"  key {i} ({k['mode']}): {shown_keys[k['id']]}")
        hook_rows = [[f"w{i}", h["mode"], h["url"], "shown below" if h["id"] in shown_hooks else "hidden"] for i, h in enumerate(hooks, 1)]
        if hook_rows:
            ui.table("Webhook signing secrets", ["#", "Mode", "Endpoint", "Secret"], hook_rows)
            for i, h in enumerate(hooks, 1):
                if h["id"] in shown_hooks:
                    ui.raw(f"  secret w{i}: {shown_hooks[h['id']]}")
        ui.panel(f"Merchant id   {me['id']}\nAPI base URL  {ctx.api.base_url}\nDashboard     {me['email']}", title="Other credentials")
        sample = next(iter(shown_keys.values()), "<show a key first>")
        ui.say("Use a key like this:")
        ui.raw(f"  curl -X POST {ctx.api.base_url}/v1/collections -H \"Authorization: Bearer {sample}\" "
               "-H \"Content-Type: application/json\" -H \"Idempotency-Key: order-1001\" "
               "-d '{\"amount\":5000,\"phone\":\"670000001\"}'")
        cmd = ui.ask("\nCommand: number = show/hide key, w+number = show/hide webhook secret, c = create key, r = revoke key, b = back",
                     default="b").strip().lower()
        if cmd == "b":
            return
        if cmd.isdigit() and 1 <= int(cmd) <= len(keys):
            k = keys[int(cmd) - 1]
            if k["id"] in shown_keys:
                del shown_keys[k["id"]]
            else:
                try:
                    shown_keys[k["id"]] = ctx.api.request("GET", f"/me/api-keys/{k['id']}/secret")["secret"]
                    mark(ctx, "key_viewed")
                except ApiError as exc:
                    ui.warn(exc.message)
                    ui.pause()
        elif cmd.startswith("w") and cmd[1:].isdigit() and 1 <= int(cmd[1:]) <= len(hooks):
            h = hooks[int(cmd[1:]) - 1]
            if h["id"] in shown_hooks:
                del shown_hooks[h["id"]]
            else:
                shown_hooks[h["id"]] = ctx.api.request("GET", f"/me/webhook-endpoints/{h['id']}/secret")["signing_secret"]
        elif cmd == "c":
            mode = ui.ask("Mode", choices=["test", "live"], default=ctx.mode)
            label = ui.ask("Label", default="my key")
            created = ctx.api.request("POST", "/me/api-keys", json={"mode": mode, "label": label})
            shown_keys[created["id"]] = created["secret"]
            ctx.api.forget_keys()
            mark(ctx, "key_viewed")
        elif cmd == "r":
            n = ui.ask("Number of the key to revoke", default="")
            if n.isdigit() and 1 <= int(n) <= len(keys) and ui.confirm(f"Revoke key {n}? Apps using it stop working.", default=False):
                ctx.api.request("DELETE", f"/me/api-keys/{keys[int(n) - 1]['id']}")
                ctx.api.forget_keys()
                shown_keys.pop(keys[int(n) - 1]["id"], None)


# ------------------------------------------------------------------ apps (Campay-style credentials)
def apps_screen(ctx: Ctx) -> None:
    shown: dict[str, dict] = {}
    while True:
        ui.clear()
        apps = ctx.api.request("GET", "/me/apps")["data"]
        ui.panel("An app gives you Campay-style credentials: an app username, an app password and a webhook key.\n"
                 "Point any Campay-style client (or the demo server in merchant_app/) at the API base URL and it works like Campay:\n"
                 "POST /token/, POST /collect/, POST /withdraw/, GET /transaction/{reference}/, GET /balance/, POST /get_payment_link/.",
                 title="Apps")
        if apps:
            ui.table("Your apps", ["#", "Name", "Mode", "Username", "Webhook URL", "Credentials"],
                     [[i, a["name"], a["mode"], a["username"], a["webhook_url"] or "-",
                       "[dim]revoked[/dim]" if a["revoked_at"] else "shown below" if a["id"] in shown else "hidden" if a["revealable"] else "cannot be shown"]
                      for i, a in enumerate(apps, 1)])
            for i, a in enumerate(apps, 1):
                if a["id"] in shown:
                    c = shown[a["id"]]
                    ui.raw(f"  app {i}  username     : {c['username']}")
                    ui.raw(f"         password     : {c['password']}")
                    ui.raw(f"         webhook key  : {c['webhook_key']}")
                    ui.raw(f"         API base URL : {c['api_base_url']}")
        else:
            ui.say("No apps yet.")
        cmd = ui.ask("\nCommand: number = show/hide credentials, n = new app, u = set webhook URL, r = revoke, b = back", default="b").strip().lower()
        if cmd == "b":
            return
        if cmd == "n":
            name = ui.ask("App name", default="my app")
            mode = ui.ask("Mode", choices=["test", "live"], default=ctx.mode)
            url = ui.ask("Webhook URL (Enter to skip; the demo server uses http://localhost:9000/webhooks/paysawa)", default="").strip()
            body = {"name": name, "mode": mode}
            if url:
                body["webhook_url"] = url
            created = ctx.api.request("POST", "/me/apps", json=body)
            shown[created["id"]] = ctx.api.request("GET", f"/me/apps/{created['id']}/credentials")
            mark(ctx, "app_created")
        elif cmd.isdigit() and 1 <= int(cmd) <= len(apps):
            a = apps[int(cmd) - 1]
            if a["id"] in shown:
                del shown[a["id"]]
            else:
                shown[a["id"]] = ctx.api.request("GET", f"/me/apps/{a['id']}/credentials")
        elif cmd == "u":
            n = ui.ask("Number of the app", default="1")
            if n.isdigit() and 1 <= int(n) <= len(apps):
                url = ui.ask("New webhook URL (empty = remove)", default="").strip()
                ctx.api.request("PATCH", f"/me/apps/{apps[int(n) - 1]['id']}", json={"webhook_url": url})
        elif cmd == "r":
            n = ui.ask("Number of the app to revoke", default="")
            if n.isdigit() and 1 <= int(n) <= len(apps) and ui.confirm("Revoke this app? Everything using its credentials stops working.", default=False):
                ctx.api.request("DELETE", f"/me/apps/{apps[int(n) - 1]['id']}")
                shown.pop(apps[int(n) - 1]["id"], None)


# ------------------------------------------------------------------ webhooks
def verify_signature(secret: str, body: bytes, header_value: str, tolerance: int = 300) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in header_value.split(","))
        stamp, given = int(parts["t"]), parts["v1"]
    except (KeyError, ValueError):
        return False
    if abs(time.time() - stamp) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, given)


class Receiver:
    """Tiny local webhook receiver used by the Listen demo."""

    def __init__(self, port: int):
        self.secret = ""
        self.valid = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                outer.handle(body, self.headers.get("X-Paysawa-Signature", ""))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def handle(self, body: bytes, signature: str) -> None:
        valid = verify_signature(self.secret, body, signature)
        try:
            data = json.loads(body)
            line = f"{data['type']}  id={data['data']['id']}  amount={data['data']['amount']}  status={data['data']['status']}"
        except (ValueError, KeyError):
            line = "unreadable payload"
        self.valid += 1 if valid else 0
        ui.say(f"  [cyan]webhook[/cyan] {line}  signature " + ("[green]VALID[/green]" if valid else "[red]INVALID[/red]"))

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def listen(ctx: Ctx) -> None:
    if ctx.mode != "test":
        ui.warn("Listen mode is for TEST mode. In live mode register a public https URL instead.")
        ui.pause()
        return
    port = int(ui.ask("Local port to listen on", default="9009"))
    try:
        receiver = Receiver(port)
    except OSError:
        ui.err(f"Port {port} is busy. Pick another one.")
        ui.pause()
        return
    try:
        created = ctx.api.request("POST", "/me/webhook-endpoints", json={"mode": "test", "url": f"http://127.0.0.1:{port}/hook", "events": []})
    except ApiError as exc:
        receiver.stop()
        if exc.status == 422:
            ui.panel("The server refused a localhost URL (protection against attacks on private addresses).\n"
                     "For development, add ALLOW_PRIVATE_WEBHOOK_URLS=true to the server's .env and restart it,\n"
                     "or expose this port publicly (for example `ngrok http " + str(port) + "`) and register that https URL.",
                     title="Cannot listen on localhost", style="yellow")
            ui.pause()
            return
        raise
    receiver.secret = created["signing_secret"]
    try:
        ui.panel(f"Listening on http://127.0.0.1:{port}/hook. Every Paysawa event for your TEST account appears here with its "
                 "signature check.", title="Webhook listener", style="cyan")
        while True:
            cmd = ui.ask("d = test deposit, f = failing deposit, p = withdrawal, Enter = stop", default="").strip().lower()
            if not cmd:
                break
            try:
                if cmd == "d":
                    call_collect(ctx, "670000001", 5000, desc="webhook demo")
                elif cmd == "f":
                    call_collect(ctx, "670000000", 3000, desc="webhook demo (fails)")
                elif cmd == "p":
                    call_payout(ctx, "690000001", 1000, desc="webhook demo")
                else:
                    continue
            except ApiError as exc:
                ui.err(exc.message)
                continue
            time.sleep(2)
    finally:
        try:
            ctx.api.request("DELETE", f"/me/webhook-endpoints/{created['id']}")
        except ApiError:
            pass
        receiver.stop()
    if receiver.valid:
        mark(ctx, "webhook_received")
        ui.ok(f"{receiver.valid} signed webhook(s) received and verified. Listener removed.")
        ui.pause()


def webhooks_screen(ctx: Ctx) -> None:
    shown: dict[str, str] = {}
    while True:
        ui.clear()
        hooks = ctx.api.request("GET", "/me/webhook-endpoints")["data"]
        ui.panel("A webhook is Paysawa calling YOUR server when something happens (deposit succeeded, withdrawal failed...). "
                 "Each call is signed so you can prove it came from Paysawa.", title="Webhooks")
        if hooks:
            ui.table("Your endpoints", ["#", "Mode", "URL", "Events"],
                     [[i, h["mode"], h["url"], ", ".join(h["events"]) or "all"] for i, h in enumerate(hooks, 1)])
            for i, h in enumerate(hooks, 1):
                if h["id"] in shown:
                    ui.raw(f"  signing secret {i}: {shown[h['id']]}")
        else:
            ui.say("No endpoints yet.")
        cmd = ui.ask("\nl = listen here (demo), r = register URL, d = delete, v = recent deliveries, number = show/hide secret, b = back",
                     default="b").strip().lower()
        if cmd == "b":
            return
        if cmd == "l":
            listen(ctx)
        elif cmd == "r":
            url = ui.ask("Public URL that will receive events")
            created = ctx.api.request("POST", "/me/webhook-endpoints", json={"mode": ctx.mode, "url": url, "events": []})
            shown[created["id"]] = created["signing_secret"]
            ui.ok("Endpoint registered. Its signing secret is listed under it.")
        elif cmd == "d":
            n = ui.ask("Number to delete", default="")
            if n.isdigit() and 1 <= int(n) <= len(hooks):
                ctx.api.request("DELETE", f"/me/webhook-endpoints/{hooks[int(n) - 1]['id']}")
        elif cmd == "v":
            rows = ctx.api.request("GET", "/me/webhook-deliveries", params={"limit": 15})["data"]
            ui.table("Recent deliveries", ["Event", "Status", "Attempts", "Last HTTP", "When"],
                     [[d["event"], colored(d["status"]), d["attempts"], d["last_status_code"] or "-",
                       (d["created_at"] or "")[:19].replace("T", " ")] for d in rows])
            ui.pause()
        elif cmd.isdigit() and 1 <= int(cmd) <= len(hooks):
            h = hooks[int(cmd) - 1]
            if h["id"] in shown:
                del shown[h["id"]]
            else:
                shown[h["id"]] = ctx.api.request("GET", f"/me/webhook-endpoints/{h['id']}/secret")["signing_secret"]


# ------------------------------------------------------------------ checkout sessions
def watch_session(ctx: Ctx, sid: str) -> None:
    ui.say("Open the link, enter a number (test: 670000001) and pay. I will tell you when it is done. Ctrl+C stops watching.")
    view = {}
    try:
        with ui.spinner("Waiting for the payment on the pay page..."):
            deadline = time.time() + 300
            while time.time() < deadline:
                view = ctx.api.request("GET", f"/gate/sessions/{sid}/status", auth="none")
                if view["status"] in ("paid", "expired"):
                    break
                time.sleep(2)
    except KeyboardInterrupt:
        ui.say("Stopped watching.")
        return
    if view.get("status") == "paid":
        ui.ok("Paid. The customer completed the payment on the pay page and your balance was credited.")
        mark(ctx, "session_paid")
        mark(ctx, "pay_page")
    elif view.get("status") == "expired":
        ui.warn("The link expired before anyone paid.")
    else:
        ui.warn("Not paid yet. You can check it later with option 3.")


def sessions_screen(ctx: Ctx) -> None:
    while True:
        ui.clear()
        ui.panel("A checkout session is a payment link for one amount. Your customer opens it on the hosted pay page "
                 "(built next), enters their phone and approves. Here you can create one and play the customer yourself.",
                 title="Checkout sessions")
        choice = ui.ask("1 = create a session, 2 = be the customer, 3 = check a session, b = back",
                        choices=["1", "2", "3", "b"], default="b")
        if choice == "b":
            return
        if choice == "1":
            amount = ask_amount(default="2000")
            desc = ui.ask("Description", default="Order 1001")
            raw_minutes = ui.ask("Link valid for how many minutes (1-1440)", default="60").strip()
            minutes = int(raw_minutes) if raw_minutes.isdigit() and 1 <= int(raw_minutes) <= 1440 else 60
            redirect = ui.ask("Redirect URL after payment (Enter to skip)", default="").strip()
            body = {"amount": amount, "description": desc, "merchant_reference": f"cli-{uuid.uuid4().hex[:6]}", "expires_in_minutes": minutes}
            if redirect:
                body["redirect_url"] = redirect
            cs = ctx.api.request("POST", "/v1/checkout-sessions", auth="key", key=key_of(ctx), json=body)
            ctx.last_session = cs["id"]
            ui.panel(f"id       {cs['id']}\namount   {fmt(cs['amount'])} XAF\ncreated  {local_time(cs['created_at'])}\n"
                     f"expires  {local_time(cs['expires_at'])}   (valid for {minutes} min)\n[dim]times are shown in your local timezone; the server stores UTC[/dim]",
                     title="Session created", style="green")
            url = cs["url"]
            if not url.startswith(ctx.api.base_url):  # APP_BASE_URL on the server differs from the server you are talking to
                url = f"{ctx.api.base_url}/pay/{cs['id']}"
            ui.say("Pay page link:")
            ui.raw("  " + url)
            if ui.confirm("Open the pay page in your browser now?", default=True):
                webbrowser.open(url)
            if ui.confirm("Watch this session here until it is paid?", default=True):
                watch_session(ctx, cs["id"])
            ui.pause()
        elif choice == "2":
            sid = ui.ask("Session id", default=ctx.last_session or "").strip()
            phone = ask_phone(ctx, "Customer phone")
            ctx.api.request("POST", f"/gate/sessions/{sid}/pay", auth="none", json={"phone": phone})
            view = None
            with ui.spinner("Customer is approving..."):
                for _ in range(15):
                    view = ctx.api.request("GET", f"/gate/sessions/{sid}/status", auth="none")
                    if view["status"] != "open" or (view.get("payment") or {}).get("status") in ("succeeded", "failed"):
                        break
                    time.sleep(2)
            pay = view.get("payment") or {}
            ui.panel(f"session  {colored(view['status'])}\npayment  {colored(pay.get('status', '-'))}"
                     + (f"\nreason   {pay['failure_message']}" if pay.get("failure_message") else "")
                     + f"\nattempts left {view['attempts_left']}", title="Customer view")
            if view["status"] == "paid":
                mark(ctx, "session_paid")
            ui.pause()
        else:
            sid = ui.ask("Session id", default=ctx.last_session or "").strip()
            view = ctx.api.request("GET", f"/gate/sessions/{sid}", auth="none")
            left = view.get("expires_in_seconds", 0)
            ui.panel(f"merchant {view['merchant_name']}\namount   {fmt(view['amount'])} {view['currency']}\n"
                     f"status   {colored(view['status'])}\nexpires  {local_time(view['expires_at'])}"
                     + (f"   (in {max(1, round(left / 60))} min)" if view["status"] == "open" else "")
                     + f"\nattempts left {view['attempts_left']}", title=sid)
            ui.pause()


# ------------------------------------------------------------------ sandbox lab
def _attempt(ctx: Ctx, method: str, path: str, **kw):
    """Returns (http_status, body) without raising on API errors."""
    try:
        data = ctx.api.request(method, path, auth="key", key=key_of(ctx), **kw)
        return ctx.api.last_status, data
    except ApiError as exc:
        return exc.status, {"error": {"code": exc.code, "message": exc.message}}


def _result(title: str, expect: str, got: str, passed: bool) -> bool:
    ui.say(f"[bold]{title}[/bold]\n  expected: {expect}\n  got:      {got}\n  " + ("[green]PASS[/green]" if passed else "[red]FAIL[/red]") + "\n")
    return passed


def _ensure_funds(ctx: Ctx, needed: int) -> None:
    if my_balance(ctx)["available"] < needed:
        ui.say(f"  (adding sandbox money first: a 5 000 XAF test deposit)")
        _attempt(ctx, "POST", "/v1/collections", headers={"Idempotency-Key": f"lab-{uuid.uuid4().hex[:8]}"},
                 json={"amount": 5000, "phone": "670000001"})


def lab_success_deposit(ctx: Ctx) -> bool:
    code, tx = _attempt(ctx, "POST", "/v1/collections", headers={"Idempotency-Key": f"lab-{uuid.uuid4().hex[:8]}"},
                        json={"amount": 5000, "phone": "670000001"})
    passed = code == 201 and tx.get("status") == "succeeded"
    if passed:
        mark(ctx, "deposit_ok")
    return _result("1. Successful deposit", "status succeeded, balance +5 000 minus fee", f"HTTP {code}, status {tx.get('status')}", passed)


def lab_failed_deposit(ctx: Ctx) -> bool:
    code, tx = _attempt(ctx, "POST", "/v1/collections", headers={"Idempotency-Key": f"lab-{uuid.uuid4().hex[:8]}"},
                        json={"amount": 3000, "phone": "670000000"})
    passed = code == 201 and tx.get("status") == "failed"
    if passed:
        mark(ctx, "deposit_failed")
    return _result("2. Failed deposit (number ends in 0000)", "status failed, balance unchanged", f"HTTP {code}, status {tx.get('status')}", passed)


def lab_pending_deposit(ctx: Ctx) -> bool:
    if not ui.confirm("This leaves one deposit pending forever in your history. Run it?", default=False):
        return True
    code, tx = _attempt(ctx, "POST", "/v1/collections", headers={"Idempotency-Key": f"lab-{uuid.uuid4().hex[:8]}"},
                        json={"amount": 3000, "phone": "670009999"})
    return _result("3. Pending deposit (number ends in 9999)", "status pending, balance unchanged", f"HTTP {code}, status {tx.get('status')}",
                   code == 201 and tx.get("status") == "pending")


def lab_idempotency(ctx: Ctx) -> bool:
    headers = {"Idempotency-Key": f"lab-{uuid.uuid4().hex[:8]}"}
    body = {"amount": 5000, "phone": "670000001"}
    c1, t1 = _attempt(ctx, "POST", "/v1/collections", headers=headers, json=body)
    c2, t2 = _attempt(ctx, "POST", "/v1/collections", headers=headers, json=body)
    c3, t3 = _attempt(ctx, "POST", "/v1/collections", headers=headers, json={**body, "amount": 6000})
    passed = c1 == 201 and c2 == 200 and t1.get("id") == t2.get("id") and c3 == 409
    if passed:
        mark(ctx, "idempotency")
    return _result("4. Idempotency (retrying safely)",
                   "same request twice = ONE charge (second answer is 200, same id); same key with another amount = 409",
                   f"first {c1}, replay {c2} (same id: {t1.get('id') == t2.get('id')}), changed amount {c3}", passed)


def lab_payout_success(ctx: Ctx) -> bool:
    _ensure_funds(ctx, 2000)
    code, tx = _attempt(ctx, "POST", "/v1/payouts", headers={"Idempotency-Key": f"lab-{uuid.uuid4().hex[:8]}"},
                        json={"amount": 1000, "phone": "690000001"})
    passed = code == 201 and tx.get("status") == "succeeded"
    if passed:
        mark(ctx, "payout_ok")
    return _result("5. Withdrawal to an Orange number", "status succeeded, balance -1 000 minus fee", f"HTTP {code}, status {tx.get('status')}", passed)


def lab_payout_refund(ctx: Ctx) -> bool:
    _ensure_funds(ctx, 2000)
    before = my_balance(ctx)
    code, tx = _attempt(ctx, "POST", "/v1/payouts", headers={"Idempotency-Key": f"lab-{uuid.uuid4().hex[:8]}"},
                        json={"amount": 1000, "phone": "670000000"})
    after = my_balance(ctx)
    restored = after["available"] == before["available"] and after["held"] == before["held"]
    passed = code == 201 and tx.get("status") == "failed" and restored
    if passed:
        mark(ctx, "payout_refund")
    return _result("6. Failed withdrawal refunds itself", "status failed, balance exactly as before, nothing held",
                   f"HTTP {code}, status {tx.get('status')}, balance restored: {restored}", passed)


def lab_insufficient(ctx: Ctx) -> bool:
    available = my_balance(ctx)["available"]
    code, body = _attempt(ctx, "POST", "/v1/payouts", headers={"Idempotency-Key": f"lab-{uuid.uuid4().hex[:8]}"},
                          json={"amount": available + 1000, "phone": "670000001"})
    passed = code == 402 and body.get("error", {}).get("code") == "insufficient_funds"
    if passed:
        mark(ctx, "payout_refused")
    return _result("7. Withdrawing more than you own", "HTTP 402 insufficient_funds",
                   f"HTTP {code} {body.get('error', {}).get('code', body.get('status'))}", passed)


LAB = [
    ("1", "Successful deposit", lab_success_deposit),
    ("2", "Failed deposit", lab_failed_deposit),
    ("3", "Pending deposit (leaves a pending item)", lab_pending_deposit),
    ("4", "Idempotency replay", lab_idempotency),
    ("5", "Withdrawal to an Orange number", lab_payout_success),
    ("6", "Failed withdrawal refund", lab_payout_refund),
    ("7", "Withdraw more than you own", lab_insufficient),
]


def sandbox_lab(ctx: Ctx) -> None:
    if ctx.mode != "test":
        ui.warn("The sandbox lab only runs in TEST mode (menu 8 to switch).")
        ui.pause()
        return
    ui.panel("Each scenario fires real API calls at the simulated provider and tells you what should happen.\n"
             + "\n".join(f"{n}  {title}" for n, title, _ in LAB) + "\na  run 1, 2, 4, 5, 6 and 7", title="Sandbox lab")
    choice = ui.ask("Scenario", choices=[n for n, _, _ in LAB] + ["a", "b"], default="a")
    if choice == "b":
        return
    if choice == "a":
        results = [fn(ctx) for n, _, fn in LAB if n in ("1", "2", "4", "5", "6", "7")]
        ui.say(f"[bold]{sum(results)} of {len(results)} scenarios passed.[/bold]")
    else:
        dict((n, fn) for n, _, fn in LAB)[choice](ctx)
    ui.pause()


# ------------------------------------------------------------------ mode and checklist
def switch_mode(ctx: Ctx) -> None:
    if ctx.mode == "live":
        ctx.mode = "test"
        ui.ok("Back in TEST mode.")
        ui.pause()
        return
    me = get_me(ctx, refresh=True)
    mark(ctx, "live_viewed")
    if not me["live_enabled"]:
        ui.panel("LIVE mode is OFF for this account. It moves real money, so it is enabled per account with limits.\n"
                 f"Ask the Paysawa admin to run:\n  python -m scripts.admin enable-live --email {me['email']} --per-txn 50000 --daily 200000",
                 title="Live mode not enabled", style="yellow")
        ui.pause()
        return
    ui.panel(f"LIVE mode uses real MTN / Orange Money.\nLimits: {fmt(me['limits']['per_transaction'])} XAF per transaction, "
             f"{fmt(me['limits']['daily'])} XAF per day.", title="Switch to LIVE", style="red")
    if ui.confirm("Switch to LIVE mode?", default=False):
        ctx.mode = "live"


def checklist(ctx: Ctx) -> None:
    finished = state.done(ctx.cfg, ctx.email)
    ui.table("Things to try (in order)", ["", "What", "How"],
             [["[green]done[/green]" if flag in finished else "todo", title, how] for flag, title, how in state.CHECKLIST])
    ui.pause()


# ------------------------------------------------------------------ main loop
def guarded(ctx: Ctx, fn) -> None:
    try:
        fn(ctx)
    except ApiError as exc:
        if exc.status == 401 and ctx.email:
            logout(ctx, silent=True)
            ui.err("Your session expired. Please log in again.")
        else:
            ui.err(f"{exc.code}: {exc.message}")
        ui.pause()
    except KeyboardInterrupt:
        ui.say("")


LOGGED_OUT = {"1": signup, "2": login, "3": change_server}
LOGGED_IN = {"a": apps_screen, "1": deposit, "2": withdraw, "3": balance_screen, "4": keys_screen, "5": webhooks_screen,
             "6": sessions_screen, "7": sandbox_lab, "8": switch_mode, "9": checklist}


def main() -> None:
    cfg = state.load()
    url = os.environ.get("PAYSAWA_URL") or cfg.get("base_url") or "http://localhost:8000"
    api = Api(url, cfg.get("token"))
    ctx = Ctx(cfg, api)
    if cfg.get("token"):
        try:
            ctx.me = api.request("GET", "/me")
            ctx.email = ctx.me["email"]
        except ApiError as exc:
            if exc.status == 401:
                logout(ctx, silent=True)
    try:
        while True:
            try:
                header(ctx)
            except ApiError:
                logout(ctx, silent=True)
                ui.err("Your session expired. Please log in again.")
                continue
            if not ctx.email:
                ui.say("1 Sign up    2 Log in    3 Change server    q Quit")
                choice = ui.ask("Choose", choices=["1", "2", "3", "q"], default="2")
                if choice == "q":
                    break
                guarded(ctx, LOGGED_OUT[choice])
            else:
                ui.say("1 Deposit (collect)    2 Withdraw (payout)    3 Balance & history    4 Keys & credentials\n"
                       "5 Webhooks    6 Checkout sessions    7 Sandbox lab    8 Switch TEST/LIVE    9 Checklist    a Apps\n"
                       "l Log out    q Quit")
                choice = ui.ask("Choose", choices=list(LOGGED_IN) + ["l", "q"], default="9")
                if choice == "q":
                    break
                if choice == "l":
                    logout(ctx)
                    continue
                guarded(ctx, LOGGED_IN[choice])
    except KeyboardInterrupt:
        pass
    state.save(ctx.cfg)
    ui.say("Bye.")


if __name__ == "__main__":
    main()
