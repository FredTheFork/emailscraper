"""SerpApi Multi-Engine Harvester — Google Maps, Google, Bing, Bing Maps, DuckDuckGo & Yahoo.

Queries `https://serpapi.com/search.json` starting with `google_maps` (20 verified local
businesses per page with direct `website` URLs) and `bing_maps` / `google` / `bing` for
trade suppliers and manufacturers, using `SERPAPI_API_KEY`.
"""

from __future__ import annotations

from typing import Any

from window_harvester.geo import COUNTRY_TO_LANG
from window_harvester.http_client import make_sync_client, request_with_retry
from window_harvester.sources.base import BaseSource

SERPAPI_URL = "https://serpapi.com/search.json"


def parse_serpapi_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract business websites from any SerpApi engine (google_maps, bing_maps, google, bing, ddg)."""
    out: list[dict[str, Any]] = []

    # 1. Google Maps / Bing Maps / Local pack results
    local = data.get("local_results")
    if isinstance(local, dict):
        local = local.get("places") or []
    if isinstance(local, list):
        for p in local:
            if not isinstance(p, dict):
                continue
            links = p.get("links") if isinstance(p.get("links"), dict) else {}
            web = str(p.get("website") or links.get("website") or "").strip()
            if not web:
                continue
            gps = p.get("gps_coordinates") if isinstance(p.get("gps_coordinates"), dict) else {}
            out.append(
                {
                    "url": web,
                    "business_name": str(p.get("title") or ""),
                    "title": str(p.get("title") or ""),
                    "snippet": str(p.get("description") or ""),
                    "category_hint": str(p.get("type") or ""),
                    "address": str(p.get("address") or ""),
                    "phone": str(p.get("phone") or ""),
                    "lat": float(gps["latitude"]) if gps.get("latitude") is not None else None,
                    "lon": float(gps["longitude"]) if gps.get("longitude") is not None else None,
                    "trust": "medium",
                }
            )

    # 2. Organic web results (google, bing, duckduckgo, yahoo)
    for item in data.get("organic_results") or []:
        if isinstance(item, dict) and item.get("link"):
            out.append(
                {
                    "url": str(item["link"]),
                    "business_name": "",
                    "title": str(item.get("title") or ""),
                    "snippet": str(item.get("snippet") or ""),
                    "category_hint": "",
                    "address": "",
                    "phone": "",
                    "lat": None,
                    "lon": None,
                    "trust": "low",
                }
            )
    return out


class SerpApiSource(BaseSource):
    """Multi-engine harvester (Google Maps, Google, Bing & Bing Maps) powered by SerpApi."""

    name = "serpapi"
    display_name = "SerpApi (Google Maps + Google + Bing + Bing Maps)"
    requires_api_key = True
    is_free = False
    estimated_yield = "50,000 – 350,000+ URLs"
    description = (
        "Queries Google Maps (local listings with website links) plus Google & Bing Organic "
        "results across {keyword} × {location} using SERPAPI_API_KEY."
    )
    flush_size = 300

    def is_available(self) -> tuple[bool, str]:
        if self.config.serpapi_api_key:
            return (True, "ready")
        return (False, "Set SERPAPI_API_KEY (https://serpapi.com)")

    def _run_impl(self) -> None:
        if not self.config.serpapi_api_key:
            raise RuntimeError("SERPAPI_API_KEY is required for serpapi source.")

        tasks = self.build_search_matrix(include_trade_queries=True)
        done = self.db.get_done_checkpoints(self.name)
        max_pages = max(1, min(self.config.max_pages_per_query, 5))

        with make_sync_client(timeout=40.0) as client:
            for idx, task in enumerate(tasks, start=1):
                if self.should_stop():
                    break
                cp_key = task["key"]
                if cp_key in done:
                    self.result.tasks_skipped_checkpoint += 1
                    continue

                cc = task["country"].lower()
                hl = COUNTRY_TO_LANG.get(task["country"], "en")
                query = task["query"]
                engine = "google" if task.get("is_trade") else "google_maps"
                before_added = self.result.new_domains_added
                failed = False

                for page in range(max_pages):
                    params: dict[str, Any] = {
                        "api_key": self.config.serpapi_api_key,
                        "engine": engine,
                        "q": query,
                        "gl": cc,
                        "hl": hl,
                    }
                    if engine == "google_maps":
                        params["type"] = "search"
                        if page > 0:
                            params["start"] = page * 20
                    else:
                        params["num"] = 50
                        if page > 0:
                            params["start"] = page * 50

                    try:
                        resp = request_with_retry(client, "GET", SERPAPI_URL, params=params, max_retries=2)
                        if resp.status_code != 200:
                            self.result.errors += 1
                            failed = True
                            break
                        items = parse_serpapi_response(resp.json())
                    except Exception:
                        self.result.errors += 1
                        failed = True
                        break

                    for it in items:
                        self.ingest_candidate(
                            it["url"],
                            business_name=it["business_name"],
                            title=it["title"],
                            snippet=it["snippet"],
                            category_hint=it["category_hint"] or task["keyword"],
                            source_trust=it["trust"],
                            country=task["country"],
                            region=task.get("region") or None,
                            city=task.get("city") or None,
                            postcode=task.get("postcode") or None,
                            address=it["address"],
                            phone=it["phone"],
                            lat=it["lat"],
                            lon=it["lon"],
                            sample_query=f"serpapi_{engine}:{query}",
                        )
                    if len(items) < 12:
                        break

                self.flush()
                found_here = self.result.new_domains_added - before_added
                if not failed:
                    self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
                self.result.tasks_completed += 1

                if self.result.tasks_completed % 10 == 0 or found_here >= 5:
                    self.emit_progress(
                        f"[{idx:,}/{len(tasks):,}] SerpApi '{query}' -> +{found_here} new "
                        f"(total: +{self.result.new_domains_added:,})"
                    )
