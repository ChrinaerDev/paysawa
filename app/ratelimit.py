import time
from collections import defaultdict, deque

from fastapi import Request

from app.errors import ApiError


class RateLimiter:
    """In-memory sliding window. Fine for a single instance; resets on restart."""

    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.max_calls:
            raise ApiError(429, "rate_limited", "Too many requests, slow down.")
        hits.append(now)
        if len(self._hits) > 10_000:  # crude memory bound
            self._hits.clear()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
