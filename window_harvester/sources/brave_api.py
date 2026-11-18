"""Official Brave Search API Harvester — Independent Global Web Index.

Brave operates its own independent multi-billion-page crawler (not a wrapper on Google or Bing),
making it a superb source for uncovering regional window installers, fabricators, and trade
suppliers across 30+ countries via `GET https://api.search.brave.com/res/v1/web/search`.
"""

from __future__ import annotations

from typing import Any

from window_harvester.http_client import make_sync_client, polite_sleep, request_with_retry
from window_harvester.sources.base import BaseSource

BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# ISO-2 countries officially accepted by Brave's `country` query parameter
_BRAVE_SUPPORTED_COUNTRIES: frozenset[str] = frozenset(
    {
        "AR", "AU", "AT", "BE", "BR", "CA", "CL", "DK", "FI", "FR", "DE",
        "HK", "IN", "ID", "IT", "JP", "KR", "MY", "MX", "NL", "NZ", "NO",
        "CN", "PL", "PT", "PH", "RU", "SA", "ZA", "ES", "SE", "CH", "TW",
        "TR", "GB", "US",
    }
)


def parse_brave_web_response(data: dict[str, Any]) -> list[dict[str, str]]:
    """Extract web & local-location URLs from a Brave Web Search API JSON response."""
    out: list[dict[str, str]] = []
    web = data.get("web")
    if isinstance(web, dict):
        for item in web.get("results") or []:
            if isinstance(item, dict) and item.get("url"):
                out.append(
                    {
                        "url": str(item["url"]),
                        "title": str(item.get("title") or ""),
                        "snippet": str(item.get("description") or ""),
                        "trust": "low",
                    }
                )
    locs = data.get("locations")
    if isinstance(locs, dict):
        for item in locs.get("results") or []:
            if not isinstance(item, dict):
                continue
            contact = item.get("contact") if isinstance(item.get("contact"), dict) else {}
            u = item.get("url") or contact.get("url")
            if u:
                out.append(
                    {
                        "url": str(u),
                        "title": str(item.get("title") or ""),
                        "snippet": str(item.get("description") or ""),
                        "trust": "medium",
                    }
                )
    return out


class BraveAPISource(BaseSource):
    """Paginated window business harvester powered by the official Brave Search API."""

    name = "brave_api"
    display_name = "Official Brave Search API"
    requires_api_key = True
    is_free = False
    estimated_yield = "50,000 – 250,000+ URLs"
    description = (
        "Queries Brave's independent global web index (20 results/page, up to 10 pages/query) "
        "across {keyword} × {location} and B2B trade queries using BRAVE_API_KEY."
    )
    flush_size = 400

    def is_available(self) -> tuple[bool, str]:
        if self.config.brave_api_key:
            return (True, "ready")
        return (False, "Set BRAVE_API_KEY (https://brave.com/search/api/)")

    def _run_impl(self) -> None:
        if not self.config.brave_api_key:
            raise RuntimeError("BRAVE_API_KEY is required for brave_api source.")

        tasks = self.build_search_matrix(include_trade_queries=True)
        done = self.db.get_done_checkpoints(self.name)
        max_pages = max(1, min(self.config.max_pages_per_query, 10))

        headers = {
            "X-Subscription-Token": self.config.brave_api_key,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        }
        self.emit_progress(f"Brave Search API queue: {len(tasks):,} queries ({len(done):,} checkpointed)")

        with make_sync_client(timeout=25.0, headers=headers, http2=True) as client:
            for idx, task in enumerate(tasks, start=1):
                if self.should_stop():
                    break
                cp_key = task["key"]
                if cp_key in done:
                    self.result.tasks_skipped_checkpoint += 1
                    continue

                cc = task["country"].upper()
                query = task["query"]
                before_added = self.result.new_domains_added
                failed = False

                for offset in range(max_pages):
                    params: dict[str, Any] = {
                        "q": query,
                        "count": 20,
                        "offset": offset,
                        "safesearch": "moderate",
                    }
                    if cc in _BRAVE_SUPPORTED_COUNTRIES:
                        params["country"] = cc
                    try:
                        resp = request_with_retry(client, "GET", BRAVE_WEB_SEARCH_URL, params=params, max_retries=2)
                        if resp.status_code != 200:
                            self.result.errors += 1
                            failed = True
                            break
                        hits = parse_brave_web_response(resp.json())
                    except Exception:
                        self.result.errors += 1
                        failed = True
                        break

                    for h in hits:
                        self.ingest_candidate(
                            h["url"],
                            title=h["title"],
                            snippet=h["snippet"],
                            category_hint=task["keyword"],
                            source_trust=h["trust"],
                            country=cc,
                            region=task.get("region") or None,
                            city=task.get("city") or None,
                            postcode=task.get("postcode") or None,
                            sample_query=f"brave:{query}",
                        )
                    if len(hits) < 15:
                        break
                    polite_sleep(min(0.25, self.config.request_delay * 0.2))

                self.flush()
                found_here = self.result.new_domains_added - before_added
                if not failed:
                    self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
                self.result.tasks_completed += 1

                if self.result.tasks_completed % 10 == 0 or found_here >= 5:
                    self.emit_progress(
                        f"[{idx:,}/{len(tasks):,}] Brave '{query}' -> +{found_here} new "
                        f"(total: +{self.result.new_domains_added:,})"
                    )
