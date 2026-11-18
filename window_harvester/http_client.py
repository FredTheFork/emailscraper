"""Resilient HTTP client helpers with UA rotation, proxy pool support, backoff & jitter."""

from __future__ import annotations

import itertools
import random
import time
from typing import Any

import httpx

USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
)

RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})


class ProxyRotator:
    """Thread-friendly round-robin proxy selector."""

    def __init__(self, proxies: list[str] | None = None) -> None:
        clean = [p.strip() for p in (proxies or []) if p and p.strip()]
        self._proxies = clean
        self._cycle = itertools.cycle(clean) if clean else None

    def next(self) -> str | None:
        return next(self._cycle) if self._cycle is not None else None

    def random(self) -> str | None:
        return random.choice(self._proxies) if self._proxies else None

    def __bool__(self) -> bool:
        return bool(self._proxies)

    def __len__(self) -> int:
        return len(self._proxies)


def random_headers(*, accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8") -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": accept,
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }


def polite_sleep(base_delay: float, jitter_ratio: float = 0.35) -> None:
    if base_delay <= 0:
        return
    spread = base_delay * jitter_ratio
    time.sleep(max(0.0, base_delay + random.uniform(-spread, spread)))


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    backoff_base: float = 1.5,
    **kwargs: Any,
) -> httpx.Response:
    """Perform an HTTP request with automatic retry on transient errors, 429, and 5xx."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.request(method, url, **kwargs)
            if resp.status_code not in RETRYABLE_STATUS_CODES or attempt == max_retries:
                return resp
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = min(60.0, float(retry_after))
            else:
                wait = min(45.0, backoff_base * (2**attempt) + random.uniform(0.1, 1.2))
            time.sleep(wait)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            if attempt == max_retries:
                raise
            wait = min(45.0, backoff_base * (2**attempt) + random.uniform(0.1, 1.2))
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def make_sync_client(
    *,
    timeout: float = 30.0,
    proxy: str | None = None,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
    http2: bool = False,
) -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(timeout, connect=min(15.0, timeout)),
        proxy=proxy,
        headers=headers or random_headers(),
        follow_redirects=follow_redirects,
        http2=http2,
    )
