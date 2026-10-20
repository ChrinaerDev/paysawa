"""Serves the hosted pay page. Development convenience: in production a real frontend can host this page
elsewhere (set PAY_GATE_URL) and talk to the same /gate endpoints."""
import secrets
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)
_HTML = (Path(__file__).resolve().parent.parent / "static" / "pay.html").read_text(encoding="utf-8")


@router.get("/pay/{public_id}", response_class=HTMLResponse)
async def pay_page(public_id: str) -> HTMLResponse:
    nonce = secrets.token_urlsafe(16)
    headers = {
        "Content-Security-Policy": (
            f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
            "connect-src 'self'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        ),
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
    }
    return HTMLResponse(_HTML.replace("{{NONCE}}", nonce), headers=headers)
