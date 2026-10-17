"""SSRF guard for merchant-supplied URLs (webhook endpoints, redirect URLs)."""
import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrl(ValueError):
    pass


def check_public_url(url: str, *, allow_http: bool = False, allow_private: bool = False) -> None:
    """Blocking (does DNS). Call via asyncio.to_thread from async code."""
    parsed = urlparse(url)
    if parsed.scheme == "http" and not allow_http:
        raise UnsafeUrl("https is required in live mode")
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrl("url must start with https://")
    if not parsed.hostname:
        raise UnsafeUrl("url has no host")
    if parsed.username or parsed.password:
        raise UnsafeUrl("credentials in urls are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrl("host does not resolve") from exc
    for info in infos:
        if not allow_private and not ipaddress.ip_address(info[4][0]).is_global:
            raise UnsafeUrl("url points to a private or local address")
