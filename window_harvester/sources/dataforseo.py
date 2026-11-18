"""DataForSEO Deep SERP Harvester — Up to 300 Google Maps Listings Per Single API Call.

DataForSEO's `/v3/serp/google/maps/live/advanced` and `/v3/serp/bing/organic/live/advanced`
endpoints are purpose-built for 100,000–1,000,000+ B2B business harvesting, returning deep
paginated Google Maps (`depth: 200+`) and Google/Bing SERPs in one request.
"""

from __future__ import annotations

import base64
from typing import Any

from window_harvester.geo import COUNTRY_TO_LANG
from window_harvester.http_client import make_sync_client, request_with_retry
from window_harvester.sources.base import BaseSource

DFS_GMAPS_URL = "https://api.dataforseo.com/v3/serp/google/maps/live/advanced"
DFS_GOOGLE_ORGANIC_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"

# Official DataForSEO country `location_code` mapping
DFS_COUNTRY_LOCATION_CODES: dict[str, int] = {
    "GB": 2826, "US": 2840, "CA": 2124, "AU": 2036, "IE": 2372, "NZ": 2554, "ZA": 2710,
    "DE": 2276, "AT": 2040, "CH": 2756, "FR": 2250, "BE": 2056, "NL": 2528,
    "ES": 2724, "IT": 2380, "PT": 2620, "PL": 2616, "CZ": 2203, "SE": 2752,
    "NO": 2578, "DK": 2208, "FI": 2246, "RO": 2642, "HU": 2348, "GR": 2300,
    "SG": 2702, "AE": 2784, "IN": 2356, "MX": 2484, "BR": 2076,
}


def parse_dataforseo_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract business websites from a DataForSEO Google Maps or Organic JSON payload."""
    out: list[dict[str, Any]] = []
    for task in data.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        for res in task.get("result") or []:
            if not isinstance(res, dict):
                continue
            for item in res.get("items") or []:
                if not isinstance(item, dict):
                    continue
                item_type = str(item.get("type") or "")
                url = str(item.get("url") or item.get("domain") or "").strip()
                if not url:
                    continue
                is_maps = item_type in ("maps_search", "maps_paid_item", "local_pack")
                addr_info = item.get("address_info") if isinstance(item.get("address_info"), dict) else {}
                out.append(
                    {
                        "url": url,
                        "business_name": str(item.get("title") or "") if is_maps else "",
                        "title": str(item.get("title") or ""),
                        "snippet": str(item.get("description") or item.get("snippet") or ""),
                        "category_hint": str(item.get("category") or ""),
                        "city": str(addr_info.get("city") or ""),
                        "region": str(addr_info.get("region") or ""),
                        "postcode": str(addr_info.get("zip") or ""),
                        "address": str(item.get("address") or ""),
                        "phone": str(item.get("phone") or ""),
                        "lat": float(item["latitude"]) if item.get("latitude") is not None else None,
                        "lon": float(item["longitude"]) if item.get("longitude") is not None else None,
                        "trust": "medium" if is_maps else "low",
                    }
                )
    return out


class DataForSEOSource(BaseSource):
    """Deep Google Maps (up to 200 results/call) & Google Organic harvester via DataForSEO."""

    name = "dataforseo"
    display_name = "DataForSEO Deep Google Maps & Search API"
    requires_api_key = True
    is_free = False
    estimated_yield = "150,000 – 550,000+ URLs"
    description = (
        "Enterprise-scale Google Maps harvester returning up to 200 businesses per single query "
        "using DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD."
    )
    flush_size = 500

    def is_available(self) -> tuple[bool, str]:
        if self.config.dataforseo_login and self.config.dataforseo_password:
            return (True, "ready")
        return (False, "Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD (https://dataforseo.com)")

    def _run_impl(self) -> None:
        if not (self.config.dataforseo_login and self.config.dataforseo_password):
            raise RuntimeError("DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD are required.")

        token = base64.b64encode(
            f"{self.config.dataforseo_login}:{self.config.dataforseo_password}".encode("utf-8")
        ).decode("ascii")
        headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

        tasks = self.build_search_matrix(include_trade_queries=True)
        done = self.db.get_done_checkpoints(self.name)
        depth = min(300, max(60, self.config.max_pages_per_query * 60))

        with make_sync_client(timeout=60.0, headers=headers, http2=True) as client:
            for idx, task in enumerate(tasks, start=1):
                if self.should_stop():
                    break
                cp_key = task["key"]
                if cp_key in done:
                    self.result.tasks_skipped_checkpoint += 1
                    continue

                cc = task["country"].upper()
                loc_code = DFS_COUNTRY_LOCATION_CODES.get(cc, 2826)
                lang = COUNTRY_TO_LANG.get(cc, "en")
                query = task["query"]
                is_trade = bool(task.get("is_trade"))
                endpoint = DFS_GOOGLE_ORGANIC_URL if is_trade else DFS_GMAPS_URL

                payload = [
                    {
                        "keyword": query,
                        "location_code": loc_code,
                        "language_code": lang,
                        "depth": 100 if is_trade else depth,
                    }
                ]

                before_added = self.result.new_domains_added
                try:
                    resp = request_with_retry(client, "POST", endpoint, json=payload, max_retries=2)
                    if resp.status_code != 200:
                        self.result.errors += 1
                        continue
                    items = parse_dataforseo_response(resp.json())
                except Exception:
                    self.result.errors += 1
                    continue

                for it in items:
                    self.ingest_candidate(
                        it["url"],
                        business_name=it["business_name"],
                        title=it["title"],
                        snippet=it["snippet"],
                        category_hint=it["category_hint"] or task["keyword"],
                        source_trust=it["trust"],
                        country=cc,
                        region=it["region"] or task.get("region") or None,
                        city=it["city"] or task.get("city") or None,
                        postcode=it["postcode"] or task.get("postcode") or None,
                        address=it["address"],
                        phone=it["phone"],
                        lat=it["lat"],
                        lon=it["lon"],
                        sample_query=f"dataforseo:{query}",
                    )

                self.flush()
                found_here = self.result.new_domains_added - before_added
                self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
                self.result.tasks_completed += 1

                if self.result.tasks_completed % 5 == 0 or found_here >= 10:
                    self.emit_progress(
                        f"[{idx:,}/{len(tasks):,}] DataForSEO '{query}' -> +{found_here} new "
                        f"(total: +{self.result.new_domains_added:,})"
                    )
