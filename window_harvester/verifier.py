"""High-concurrency async HTTP website verifier, parked-domain killer & HTML classifier.

Verifies thousands of candidate domains per minute using `aiohttp`:
  1. Tries `https://{domain}` (with automatic fallback to `https://www.{domain}` and `http://{domain}`).
  2. Rejects dead DNS / timeouts (`DEAD_OR_ERROR`), domain-for-sale pages (`PARKED`),
     redirects to Facebook/Yelp/blocked domains (`IRRELEVANT`), and Microsoft Windows /
     non-building-glass sites (`IRRELEVANT`).
  3. Extracts `<title>` and `<meta name="description">`, refines window sub-categories
     (`double_triple_glazing`, `upvc_vinyl`, `timber_wood`, `aluminium`, `steel_crittall`,
     `glass_glaziers`, `manufacturers_suppliers`, etc.), and marks `LIVE_RELEVANT`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import aiohttp

from window_harvester.classifier import classify_html
from window_harvester.db import HarvestDB
from window_harvester.domains import normalize_url
from window_harvester.http_client import USER_AGENTS
from window_harvester.models import FilterOptions, VerifyStatus


@dataclass(slots=True)
class VerifySummary:
    checked: int = 0
    live_relevant: int = 0
    dead_or_error: int = 0
    parked: int = 0
    irrelevant: int = 0


async def probe_single_domain(
    session: aiohttp.ClientSession,
    domain: str,
    url: str,
    options: FilterOptions,
    *,
    timeout_s: float = 12.0,
    strict_content: bool = True,
    existing_confidence: float = 0.7,
) -> dict[str, Any]:
    """Fetch a domain's homepage and classify its live HTML."""
    candidates = [url]
    if f"://www.{domain}" not in url:
        candidates.append(f"https://www.{domain}")
    candidates.append(f"http://{domain}")

    req_timeout = aiohttp.ClientTimeout(total=timeout_s, connect=min(6.0, timeout_s))
    last_http_status: int | None = None

    for idx, target in enumerate(candidates):
        headers = {
            "User-Agent": USER_AGENTS[idx % len(USER_AGENTS)],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        }
        try:
            async with session.get(
                target,
                headers=headers,
                timeout=req_timeout,
                allow_redirects=True,
                max_redirects=6,
                ssl=False,
            ) as resp:
                last_http_status = resp.status
                final_url = str(resp.url)

                # Bot-protection challenge pages (Cloudflare 403/503) still prove the domain is alive
                if resp.status in (401, 403, 406, 429) and existing_confidence >= 0.80:
                    return {
                        "domain": domain,
                        "verified": int(VerifyStatus.LIVE_RELEVANT),
                        "http_status": resp.status,
                        "final_url": final_url,
                        "page_title": "",
                        "meta_description": "",
                        "categories": [],
                        "confidence": existing_confidence,
                    }

                if resp.status >= 400:
                    continue

                # Check if redirected onto a blocked host (e.g. hugedomains.com or facebook.com)
                final_norm = normalize_url(final_url)
                if final_norm is None:
                    return {
                        "domain": domain,
                        "verified": int(VerifyStatus.PARKED if "domain" in final_url.lower() else VerifyStatus.IRRELEVANT),
                        "http_status": resp.status,
                        "final_url": final_url,
                        "page_title": "",
                        "meta_description": "",
                        "categories": [],
                        "confidence": 0.0,
                    }

                # Read at most 200 KB of HTML so large pages never stall memory/bandwidth
                raw_bytes = await resp.content.read(204_800)
                charset = resp.charset or "utf-8"
                try:
                    html = raw_bytes.decode(charset, errors="replace")
                except LookupError:
                    html = raw_bytes.decode("utf-8", errors="replace")

                cls, title, meta_desc, is_parked = classify_html(final_url, html, options)
                if is_parked:
                    return {
                        "domain": domain,
                        "verified": int(VerifyStatus.PARKED),
                        "http_status": resp.status,
                        "final_url": final_url,
                        "page_title": title,
                        "meta_description": meta_desc,
                        "categories": [],
                        "confidence": 0.0,
                    }

                if cls.accepted:
                    return {
                        "domain": domain,
                        "verified": int(VerifyStatus.LIVE_RELEVANT),
                        "http_status": resp.status,
                        "final_url": final_url,
                        "page_title": title,
                        "meta_description": meta_desc,
                        "categories": cls.categories,
                        "confidence": round(max(existing_confidence, cls.confidence), 3),
                    }

                # Explicit Microsoft Windows / optician / auto-glass rejection
                if cls.reason in ("ms_windows_html", "ms_windows_body", "non_window_html", "auto_glass_html", "window_cleaning_html"):
                    return {
                        "domain": domain,
                        "verified": int(VerifyStatus.IRRELEVANT),
                        "http_status": resp.status,
                        "final_url": final_url,
                        "page_title": title,
                        "meta_description": meta_desc,
                        "categories": [],
                        "confidence": 0.0,
                    }

                # JS-rendered SPAs sometimes have thin server HTML; keep high-confidence POI domains alive
                if not strict_content or (existing_confidence >= 0.85 and len(html) > 500):
                    return {
                        "domain": domain,
                        "verified": int(VerifyStatus.LIVE_RELEVANT),
                        "http_status": resp.status,
                        "final_url": final_url,
                        "page_title": title,
                        "meta_description": meta_desc,
                        "categories": [],
                        "confidence": existing_confidence,
                    }

                return {
                    "domain": domain,
                    "verified": int(VerifyStatus.IRRELEVANT),
                    "http_status": resp.status,
                    "final_url": final_url,
                    "page_title": title,
                    "meta_description": meta_desc,
                    "categories": [],
                    "confidence": cls.confidence,
                }
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, UnicodeError):
            continue

    return {
        "domain": domain,
        "verified": int(VerifyStatus.DEAD_OR_ERROR),
        "http_status": last_http_status,
        "final_url": None,
        "page_title": "",
        "meta_description": "",
        "categories": [],
        "confidence": None,
    }


async def verify_database_async(
    db: HarvestDB,
    *,
    options: FilterOptions | None = None,
    concurrency: int = 120,
    limit: int = 50_000,
    timeout_s: float = 12.0,
    country: str | None = None,
    strict_content: bool = True,
    reverify_errors: bool = False,
    borderline_first: bool = True,
    on_progress: Callable[[VerifySummary], None] | None = None,
) -> VerifySummary:
    """Concurrently verify up to `limit` unverified domains in `db` and save results in batches."""
    opts = options or FilterOptions()
    rows = db.fetch_domains_for_verification(
        limit=limit,
        country=country,
        reverify_errors=reverify_errors,
        borderline_first=borderline_first,
    )
    summary = VerifySummary()
    if not rows:
        return summary

    sem = asyncio.Semaphore(max(1, concurrency))
    connector = aiohttp.TCPConnector(
        limit=max(10, concurrency),
        limit_per_host=2,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
        ssl=False,
    )

    async def _worker(session: aiohttp.ClientSession, r: Any) -> dict[str, Any]:
        async with sem:
            return await probe_single_domain(
                session,
                str(r["domain"]),
                str(r["url"]),
                opts,
                timeout_s=timeout_s,
                strict_content=strict_content,
                existing_confidence=float(r["confidence"]),
            )

    async with aiohttp.ClientSession(connector=connector) as session:
        # Process in waves of 500 so SQLite stays continuously checkpointed and memory stays tiny
        wave_size = max(100, min(500, concurrency * 4))
        for start in range(0, len(rows), wave_size):
            chunk = rows[start : start + wave_size]
            updates = await asyncio.gather(*(_worker(session, r) for r in chunk))
            db.apply_verification_batch(list(updates))

            for u in updates:
                summary.checked += 1
                v = int(u["verified"])
                if v == int(VerifyStatus.LIVE_RELEVANT):
                    summary.live_relevant += 1
                elif v == int(VerifyStatus.PARKED):
                    summary.parked += 1
                elif v == int(VerifyStatus.IRRELEVANT):
                    summary.irrelevant += 1
                else:
                    summary.dead_or_error += 1

            if on_progress:
                on_progress(summary)

    return summary


def run_verify_sync(**kwargs: Any) -> VerifySummary:
    """Run `verify_database_async` safely from both CLI scripts and Jupyter/Colab notebooks."""
    try:
        asyncio.get_running_loop()
        in_running_loop = True
    except RuntimeError:
        in_running_loop = False

    if not in_running_loop:
        return asyncio.run(verify_database_async(**kwargs))

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(verify_database_async(**kwargs))).result()

