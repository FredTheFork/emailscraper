"""Serper.dev Harvester — Ultra-Fast Google Maps & Google Search at 100k–500k+ Scale.

Serper.dev provides a free starter tier (2,500 queries) and ~$0.30–$1.00 / 1,000 queries
with zero proxy management and up to 50–300 requests/second.
  - `serper_maps`: Google Maps endpoint (`POST https://google.serper.dev/maps`) — returns 20
    real local businesses per page with `title`, `website`, `address`, `phoneNumber`,
    `type`/`types`, `latitude`, `longitude`.
  - `serper`: Runs Google Maps across the `{keyword} × {location}` grid PLUS Google Organic
    Search (`POST https://google.serper.dev/search`) for B2B manufacturers, trade suppliers,
    and accreditation queries (FENSA, CERTASS, GGF, NFRC, AGWA, REHAU, AluK, Crittall, etc.).
"""

from __future__ import annotations

from typing import Any

from window_harvester.geo import COUNTRY_TO_LANG
from window_harvester.http_client import make_sync_client, polite_sleep, request_with_retry
from window_harvester.sources.base import BaseSource

SERPER_MAPS_URL = "https://google.serper.dev/maps"
SERPER_SEARCH_URL = "https://google.serper.dev/search"


def parse_serper_maps_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract normalized business dicts from a Serper `/maps` JSON payload."""
    places = data.get("places")
    if not isinstance(places, list):
        return []
    out: list[dict[str, Any]] = []
    for p in places:
        if not isinstance(p, dict):
            continue
        web = str(p.get("website") or "").strip()
        if not web:
            continue
        types = p.get("types")
        cat = str(p.get("type") or (types[0] if isinstance(types, list) and types else "") or "")
        out.append(
            {
                "url": web,
                "business_name": str(p.get("title") or ""),
                "category_hint": cat,
                "address": str(p.get("address") or ""),
                "phone": str(p.get("phoneNumber") or ""),
                "lat": float(p["latitude"]) if p.get("latitude") is not None else None,
                "lon": float(p["longitude"]) if p.get("longitude") is not None else None,
            }
        )
    return out


def parse_serper_search_response(data: dict[str, Any]) -> list[dict[str, str]]:
    """Extract organic & local-pack business URLs from a Serper `/search` JSON payload."""
    out: list[dict[str, str]] = []
    # Local map pack embedded in organic SERP
    for p in data.get("places") or []:
        if isinstance(p, dict) and p.get("website"):
            out.append(
                {
                    "url": str(p["website"]),
                    "title": str(p.get("title") or ""),
                    "snippet": str(p.get("category") or ""),
                    "business_name": str(p.get("title") or ""),
                    "trust": "medium",
                }
            )
    # Organic results
    for item in data.get("organic") or []:
        if isinstance(item, dict) and item.get("link"):
            out.append(
                {
                    "url": str(item["link"]),
                    "title": str(item.get("title") or ""),
                    "snippet": str(item.get("snippet") or ""),
                    "business_name": "",
                    "trust": "low",
                }
            )
    return out


class SerperMapsSource(BaseSource):
    """High-speed Google Maps business website harvester via Serper.dev."""

    name = "serper_maps"
    display_name = "Google Maps via Serper.dev API"
    requires_api_key = True
    is_free = False
    estimated_yield = "100,000 – 450,000+ Google Maps URLs"
    description = (
        "High-speed Google Maps sweep across thousands of {keyword} × {city/postcode} tiles via "
        "SERPER_API_KEY (2,500 free starter queries; pulls direct business websites, phones & addresses)."
    )
    flush_size = 500
    include_organic: bool = False

    def is_available(self) -> tuple[bool, str]:
        if self.config.serper_api_key:
            return (True, "ready")
        return (False, "Set SERPER_API_KEY (free 2,500 queries at https://serper.dev)")

    def _run_impl(self) -> None:
        if not self.config.serper_api_key:
            raise RuntimeError("SERPER_API_KEY is required for Serper harvester.")

        tasks = self.build_search_matrix(include_trade_queries=self.include_organic)
        done = self.db.get_done_checkpoints(self.name)
        max_pages = max(1, min(self.config.max_pages_per_query, 6))

        headers = {
            "X-API-KEY": self.config.serper_api_key,
            "Content-Type": "application/json",
        }
        self.emit_progress(f"Serper task queue: {len(tasks):,} queries ({len(done):,} checkpointed)")

        with make_sync_client(timeout=30.0, headers=headers, http2=True) as client:
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
                before_added = self.result.new_domains_added
                failed = False

                if task.get("is_trade") and self.include_organic:
                    failed = not self._run_organic_query(client, query, cc, hl, task, max_pages)
                else:
                    failed = not self._run_maps_query(client, query, cc, hl, task, max_pages)
                    # Optionally supplement tier-1 queries with a 100-result organic SERP sweep
                    if self.include_organic and not failed and not self.should_stop():
                        self._run_organic_query(client, query, cc, hl, task, 1)

                self.flush()
                found_here = self.result.new_domains_added - before_added
                if not failed:
                    self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
                self.result.tasks_completed += 1

                if self.result.tasks_completed % 10 == 0 or found_here >= 5:
                    self.emit_progress(
                        f"[{idx:,}/{len(tasks):,}] '{query}' -> +{found_here} new "
                        f"(source total: +{self.result.new_domains_added:,})"
                    )
                if self.config.request_delay > 0:
                    polite_sleep(min(0.15, self.config.request_delay * 0.1))

    def _run_maps_query(
        self,
        client: Any,
        query: str,
        gl: str,
        hl: str,
        task: dict[str, Any],
        max_pages: int,
    ) -> bool:
        for page in range(1, max_pages + 1):
            payload: dict[str, Any] = {"q": query, "gl": gl, "hl": hl}
            if page > 1:
                payload["page"] = page
            if task.get("lat") is not None and task.get("lon") is not None:
                payload["ll"] = f"@{task['lat']},{task['lon']},12z"
            try:
                resp = request_with_retry(client, "POST", SERPER_MAPS_URL, json=payload, max_retries=2)
                if resp.status_code in (401, 403):
                    self.result.errors += 1
                    self.result.notes = f"Serper API returned HTTP {resp.status_code} (check key/credits)"
                    return False
                if resp.status_code != 200:
                    self.result.errors += 1
                    return False
                data = resp.json()
            except Exception:
                self.result.errors += 1
                return False

            raw_places = data.get("places") or []
            for item in parse_serper_maps_response(data):
                self.ingest_candidate(
                    item["url"],
                    business_name=item["business_name"],
                    category_hint=item["category_hint"] or task["keyword"],
                    source_trust="medium",
                    country=task["country"],
                    region=task.get("region") or None,
                    city=task.get("city") or None,
                    postcode=task.get("postcode") or None,
                    address=item["address"],
                    phone=item["phone"],
                    lat=item["lat"],
                    lon=item["lon"],
                    sample_query=f"serper_maps:{query}",
                )
            # Google Maps pages contain up to 20 places; fewer than 18 means last page reached
            if len(raw_places) < 18:
                break
        return True

    def _run_organic_query(
        self,
        client: Any,
        query: str,
        gl: str,
        hl: str,
        task: dict[str, Any],
        max_pages: int,
    ) -> bool:
        for page in range(1, max_pages + 1):
            payload: dict[str, Any] = {"q": query, "gl": gl, "hl": hl, "num": 30}
            if page > 1:
                payload["page"] = page
            try:
                resp = request_with_retry(client, "POST", SERPER_SEARCH_URL, json=payload, max_retries=2)
                if resp.status_code != 200:
                    self.result.errors += 1
                    return False
                data = resp.json()
            except Exception:
                self.result.errors += 1
                return False

            hits = parse_serper_search_response(data)
            for h in hits:
                self.ingest_candidate(
                    h["url"],
                    business_name=h["business_name"],
                    title=h["title"],
                    snippet=h["snippet"],
                    category_hint=task["keyword"],
                    source_trust=h["trust"],
                    country=task["country"],
                    region=task.get("region") or None,
                    city=task.get("city") or None,
                    postcode=task.get("postcode") or None,
                    sample_query=f"serper_web:{query}",
                )
            if len(hits) < 10:
                break
        return True


class SerperCombinedSource(SerperMapsSource):
    """Combined Serper Google Maps + Google Organic Web + B2B Manufacturer Search."""

    name = "serper"
    display_name = "Google Maps + Google Search via Serper.dev API"
    estimated_yield = "150,000 – 500,000+ URLs"
    description = (
        "Combines Serper Google Maps pagination + Google Organic Search + B2B trade/manufacturer "
        "queries (FENSA, CERTASS, NFRC, REHAU, AluK, Crittall, etc.) via SERPER_API_KEY."
    )
    include_organic = True
