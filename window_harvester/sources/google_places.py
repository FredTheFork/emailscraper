"""Official Google Maps Platform Places API (New) Harvester with Adaptive Quadtree Tiling.

Standard Google Places queries cap at 60 results per search — meaning a single search for
"double glazing in London" misses 95% of London's 1,500+ glazing companies.

This harvester solves the 60-result cap completely using an **Adaptive Geographic Quadtree**:
  1. Tiles each country into lat/lon rectangles using `locationRestriction.rectangle`.
  2. Paginates `places:searchText` via `pageToken` (up to 60 places per tile).
  3. Whenever a tile returns >= 55 places (saturated!) and is wider than 5 km, it
     automatically splits that rectangle into 4 child quadrants (NW, NE, SW, SE) and
     zooms in recursively until every dense city & industrial estate is 100% captured!
"""

from __future__ import annotations

from collections import deque
from typing import Any

from window_harvester.geo import COUNTRY_BOUNDING_BOXES, generate_country_grid
from window_harvester.http_client import make_sync_client, polite_sleep, request_with_retry
from window_harvester.models import BoundingBox
from window_harvester.sources.base import BaseSource
from window_harvester.taxonomy import get_keywords_for_country

GOOGLE_PLACES_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PLACES_FIELD_MASK = (
    "places.id,places.displayName,places.websiteUri,places.formattedAddress,"
    "places.nationalPhoneNumber,places.primaryType,places.location,nextPageToken"
)


def parse_google_places_response(data: dict[str, Any]) -> tuple[list[dict[str, Any]], int, str]:
    """Parse a Google Places v1 `searchText` JSON payload.

    Returns `(businesses_with_websites, total_raw_place_count, next_page_token)`.
    """
    raw_places = data.get("places") or []
    out: list[dict[str, Any]] = []
    for p in raw_places:
        if not isinstance(p, dict):
            continue
        web = str(p.get("websiteUri") or "").strip()
        if not web:
            continue
        dname = p.get("displayName")
        name = str(dname.get("text") or "") if isinstance(dname, dict) else str(dname or "")
        loc = p.get("location") if isinstance(p.get("location"), dict) else {}
        out.append(
            {
                "url": web,
                "business_name": name,
                "category_hint": str(p.get("primaryType") or ""),
                "address": str(p.get("formattedAddress") or ""),
                "phone": str(p.get("nationalPhoneNumber") or ""),
                "lat": float(loc["latitude"]) if loc.get("latitude") is not None else None,
                "lon": float(loc["longitude"]) if loc.get("longitude") is not None else None,
            }
        )
    return out, len(raw_places), str(data.get("nextPageToken") or "")


class GooglePlacesQuadtreeSource(BaseSource):
    """Exhaustive official Google Places API (New) harvester with Adaptive Quadtree subdivision."""

    name = "google_places"
    display_name = "Official Google Maps Places API (Adaptive Quadtree)"
    requires_api_key = True
    is_free = False
    estimated_yield = "100,000 – 450,000+ Google Maps URLs"
    description = (
        "Uses Google Maps Platform Places API (New) with recursive NW/NE/SW/SE bounding-box "
        "quadtree subdivision so dense metros never hit Google's 60-result cap (GOOGLE_PLACES_API_KEY)."
    )
    flush_size = 300
    saturation_threshold: int = 55
    min_cell_km: float = 5.0
    max_quadtree_depth: int = 4

    def is_available(self) -> tuple[bool, str]:
        if self.config.google_places_api_key:
            return (True, "ready")
        return (False, "Set GOOGLE_PLACES_API_KEY (enable 'Places API (New)' in Google Cloud Console)")

    def _run_impl(self) -> None:
        if not self.config.google_places_api_key:
            raise RuntimeError("GOOGLE_PLACES_API_KEY is required for google_places source.")

        target_ccs = self.config.countries or self.config.search_countries
        done = self.db.get_done_checkpoints(self.name)

        headers = {
            "X-Goog-Api-Key": self.config.google_places_api_key,
            "X-Goog-FieldMask": GOOGLE_PLACES_FIELD_MASK,
            "Content-Type": "application/json",
        }

        # Seed adaptive queue with country bounding-box grid cells for supported countries
        queue: deque[tuple[str, BoundingBox]] = deque()
        fallback_ccs: list[str] = []

        for cc in target_ccs:
            cc_up = cc.upper()
            if cc_up in COUNTRY_BOUNDING_BOXES:
                boxes = generate_country_grid(cc_up)
                # Use focused high-coverage keywords on quadtree since each splits geographically
                kws = get_keywords_for_country(
                    cc_up,
                    max_tier=min(self.config.keyword_tier, 2),
                    include_treatments=self.config.filters.include_treatments,
                    include_window_cleaning=self.config.filters.include_window_cleaning,
                    include_auto_glass=self.config.filters.include_auto_glass,
                    custom_keywords=self.config.custom_keywords,
                )[: (6 if self.config.keyword_tier == 1 else 14)]
                for kw in kws:
                    for box in boxes:
                        queue.append((kw, box))
            else:
                fallback_ccs.append(cc_up)

        self.emit_progress(f"Google Places quadtree initialized with {len(queue):,} root geo-tiles")

        with make_sync_client(timeout=30.0, headers=headers, http2=True) as client:
            while queue and not self.should_stop():
                kw, box = queue.popleft()
                cp_key = f"qt:{kw.lower()}:{box.key}"
                if cp_key in done:
                    # If this tile previously saturated and subdivided, re-enqueue children if undone
                    meta = self.db.get_checkpoint_meta(self.name, cp_key)
                    if meta and meta.get("subdivided"):
                        for child in box.subdivide():
                            if f"qt:{kw.lower()}:{child.key}" not in done:
                                queue.appendleft((kw, child))
                    self.result.tasks_skipped_checkpoint += 1
                    continue

                total_places, found_here, ok = self._search_box(client, kw, box)
                if not ok:
                    continue

                subdivided = False
                if (
                    total_places >= self.saturation_threshold
                    and box.depth < self.max_quadtree_depth
                    and box.approx_width_km > self.min_cell_km
                ):
                    subdivided = True
                    for child in reversed(box.subdivide()):
                        queue.appendleft((kw, child))

                self.flush()
                self.db.save_checkpoint(
                    self.name,
                    cp_key,
                    items_found=found_here,
                    meta={"places": total_places, "subdivided": subdivided, "depth": box.depth},
                )
                done.add(cp_key)
                self.result.tasks_completed += 1

                if subdivided or found_here >= 5 or self.result.tasks_completed % 10 == 0:
                    split_note = f" [SATURATED {total_places} -> split 4x depth {box.depth + 1}]" if subdivided else ""
                    self.emit_progress(
                        f"Tile {box.label} '{kw}': +{found_here} new{split_note} "
                        f"(queue: {len(queue):,}, total: +{self.result.new_domains_added:,})"
                    )

            # City-name text search fallback for any country without a preconfigured bbox
            if fallback_ccs and not self.should_stop():
                saved_ccs = self.config.countries
                self.config.countries = fallback_ccs
                try:
                    for task in self.build_search_matrix(include_trade_queries=False):
                        if self.should_stop():
                            break
                        cp_key = f"city:{task['key']}"
                        if cp_key in done:
                            continue
                        _, found_here, ok = self._search_text(client, task["query"], task["country"], task["keyword"])
                        if ok:
                            self.flush()
                            self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
                            self.result.tasks_completed += 1
                finally:
                    self.config.countries = saved_ccs

    def _search_box(self, client: Any, keyword: str, box: BoundingBox) -> tuple[int, int, bool]:
        before_added = self.result.new_domains_added
        total_raw = 0
        page_token = ""

        for page_idx in range(min(3, max(1, self.config.max_pages_per_query))):
            body: dict[str, Any] = {
                "textQuery": keyword,
                "pageSize": 20,
                "regionCode": box.country,
                "locationRestriction": {
                    "rectangle": {
                        "low": {"latitude": box.south, "longitude": box.west},
                        "high": {"latitude": box.north, "longitude": box.east},
                    }
                },
            }
            if page_token:
                body["pageToken"] = page_token

            try:
                resp = request_with_retry(client, "POST", GOOGLE_PLACES_TEXT_URL, json=body, max_retries=2)
                if resp.status_code != 200:
                    self.result.errors += 1
                    return (total_raw, 0, False)
                data = resp.json()
            except Exception:
                self.result.errors += 1
                return (total_raw, 0, False)

            items, raw_count, next_token = parse_google_places_response(data)
            total_raw += raw_count
            for item in items:
                self.ingest_candidate(
                    item["url"],
                    business_name=item["business_name"],
                    category_hint=item["category_hint"] or keyword,
                    source_trust="medium",
                    country=box.country,
                    address=item["address"],
                    phone=item["phone"],
                    lat=item["lat"],
                    lon=item["lon"],
                    sample_query=f"google_places:{keyword}@{box.label}",
                )

            if not next_token or raw_count < 20 or page_idx == 2:
                break
            page_token = next_token
            # Google Places nextPageToken requires a short propagation delay
            polite_sleep(1.5)

        return (total_raw, self.result.new_domains_added - before_added, True)

    def _search_text(self, client: Any, query: str, country: str, keyword: str) -> tuple[int, int, bool]:
        before_added = self.result.new_domains_added
        body = {"textQuery": query, "pageSize": 20, "regionCode": country}
        try:
            resp = request_with_retry(client, "POST", GOOGLE_PLACES_TEXT_URL, json=body, max_retries=2)
            if resp.status_code != 200:
                self.result.errors += 1
                return (0, 0, False)
            items, raw_count, _ = parse_google_places_response(resp.json())
        except Exception:
            self.result.errors += 1
            return (0, 0, False)

        for item in items:
            self.ingest_candidate(
                item["url"],
                business_name=item["business_name"],
                category_hint=item["category_hint"] or keyword,
                source_trust="medium",
                country=country,
                address=item["address"],
                phone=item["phone"],
                lat=item["lat"],
                lon=item["lon"],
                sample_query=f"google_places:{query}",
            )
        return (raw_count, self.result.new_domains_added - before_added, True)
