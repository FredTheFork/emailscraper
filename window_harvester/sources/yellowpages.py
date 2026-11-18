"""YellowPages Directory Harvester — Extracts Direct Business Websites Across All 50 US States.

Searches YellowPages.com systematically across 500+ US cities and 13 window/glazing/glass
categories, parsing both HTML listing cards (`.track-visit-website`) and embedded Schema.org
JSON-LD to pull every company's real external website URL, name, category, city, state & phone.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from window_harvester.geo import get_locations
from window_harvester.http_client import make_sync_client, polite_sleep, random_headers, request_with_retry
from window_harvester.sources.base import BaseSource
from window_harvester.taxonomy import YELLOWPAGES_US_TERMS

YP_SEARCH_URL = "https://www.yellowpages.com/search"


def parse_yellowpages_html(html: str, default_city: str = "", default_state: str = "") -> tuple[list[dict[str, Any]], bool]:
    """Extract business website listings and `has_next_page` flag from a YellowPages search HTML page."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    # 1. Standard organic & featured YellowPages business result cards
    for card in soup.select("div.result, div.v-card, div.srp-listing"):
        web_link = card.select_one("a.track-visit-website[href], a[class*='website'][href]")
        if not web_link:
            continue
        href = str(web_link.get("href") or "").strip()
        if not href or href.startswith("/") or "yellowpages.com" in href.lower():
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)

        name_el = card.select_one("a.business-name, h2.n a, .business-name span")
        bname = name_el.get_text(" ", strip=True) if name_el else ""

        cats_el = card.select(".categories a")
        cat_str = ", ".join(c.get_text(" ", strip=True) for c in cats_el) if cats_el else ""

        phone_el = card.select_one(".phones.phone.primary, .phone")
        phone = phone_el.get_text(" ", strip=True) if phone_el else ""

        street_el = card.select_one(".street-address")
        loc_el = card.select_one(".locality")
        street = street_el.get_text(" ", strip=True) if street_el else ""
        locality = loc_el.get_text(" ", strip=True) if loc_el else ""

        city = default_city
        state = default_state
        postcode = ""
        if locality and "," in locality:
            c_part, rest = locality.split(",", 1)
            city = c_part.strip() or default_city
            tokens = rest.strip().split()
            if tokens:
                state = tokens[0].strip() or default_state
            if len(tokens) >= 2:
                postcode = tokens[1].strip()

        items.append(
            {
                "url": href,
                "business_name": bname,
                "category_hint": cat_str,
                "city": city,
                "region": state,
                "postcode": postcode,
                "address": f"{street}, {locality}".strip(", "),
                "phone": phone,
            }
        )

    # 2. Also harvest Schema.org LocalBusiness entries in `<script type="application/ld+json">`
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            url = str(node.get("url") or "").strip()
            if not url or "yellowpages.com" in url.lower() or url in seen_urls:
                continue
            seen_urls.add(url)
            addr = node.get("address") if isinstance(node.get("address"), dict) else {}
            items.append(
                {
                    "url": url,
                    "business_name": str(node.get("name") or ""),
                    "category_hint": "windows",
                    "city": str(addr.get("addressLocality") or default_city),
                    "region": str(addr.get("addressRegion") or default_state),
                    "postcode": str(addr.get("postalCode") or ""),
                    "address": str(addr.get("streetAddress") or ""),
                    "phone": str(node.get("telephone") or ""),
                }
            )

    has_next = bool(soup.select_one("a.next.ajax-page[href], li.next a[href], a[rel='next']"))
    return items, has_next


class YellowPagesSource(BaseSource):
    """Harvest US window, glazing & glass business websites directly from YellowPages.com."""

    name = "yellowpages"
    display_name = "YellowPages.com Business Directory (All 50 US States)"
    requires_api_key = False
    is_free = True
    estimated_yield = "25,000 – 75,000+ US URLs"
    description = (
        "Crawls YellowPages.com across 500+ US cities and 13 window, vinyl, wood, metal, skylight "
        "& glazier categories, extracting verified external company website URLs ($0, no API key)."
    )
    flush_size = 250

    def _run_impl(self) -> None:
        if self.config.countries and "US" not in {c.upper() for c in self.config.countries}:
            self.result.notes = "Skipped (YellowPages.com covers US; US not in selected countries)"
            return

        us_locs = get_locations(["US"], max_tier=self.config.geo_tier, custom_file=self.config.custom_locations_file)
        terms = list(YELLOWPAGES_US_TERMS[: (5 if self.config.keyword_tier == 1 else len(YELLOWPAGES_US_TERMS))])
        done = self.db.get_done_checkpoints(self.name)
        max_pages = max(1, min(self.config.max_pages_per_query, 10))
        base_delay = max(1.2, self.config.request_delay)

        # Interleave terms breadth-first so every US city gets primary "windows" + "glaziers" first
        tasks = [
            (term, loc)
            for term in terms
            for loc in us_locs
        ]
        self.emit_progress(f"YellowPages US matrix: {len(tasks):,} city×category searches")

        consecutive_blocks = 0
        for idx, (term, loc) in enumerate(tasks, start=1):
            if self.should_stop():
                break
            geo_str = f"{loc.name}, {loc.region}" if loc.region else loc.name
            cp_key = f"yp:{geo_str.lower()}:{term.lower()}"
            if cp_key in done:
                self.result.tasks_skipped_checkpoint += 1
                continue

            before_added = self.result.new_domains_added
            blocked = False

            with make_sync_client(
                timeout=25.0,
                proxy=self.proxies.next(),
                headers=random_headers(),
                http2=True,
            ) as client:
                for page in range(1, max_pages + 1):
                    if self.should_stop():
                        break
                    params = {"search_terms": term, "geo_location_terms": geo_str}
                    if page > 1:
                        params["page"] = str(page)
                    url = f"{YP_SEARCH_URL}?{urlencode(params)}"
                    try:
                        resp = request_with_retry(client, "GET", url, max_retries=2)
                    except Exception:
                        self.result.errors += 1
                        blocked = True
                        break

                    if resp.status_code in (403, 429, 503):
                        self.result.errors += 1
                        blocked = True
                        consecutive_blocks += 1
                        break
                    if resp.status_code != 200:
                        break

                    consecutive_blocks = 0
                    listings, has_next = parse_yellowpages_html(resp.text, loc.name, loc.region)
                    for item in listings:
                        self.ingest_candidate(
                            item["url"],
                            business_name=item["business_name"],
                            category_hint=item["category_hint"] or term,
                            source_trust="medium",
                            country="US",
                            region=item["region"],
                            city=item["city"],
                            postcode=item["postcode"],
                            address=item["address"],
                            phone=item["phone"],
                            sample_query=f"yellowpages:{term} in {geo_str}",
                        )

                    if not has_next or not listings:
                        break
                    polite_sleep(base_delay)

            self.flush()
            found_here = self.result.new_domains_added - before_added
            if not blocked:
                self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
            elif consecutive_blocks >= 8 and not self.proxies:
                self.result.notes = (
                    "YellowPages rate-limited this IP (common on cloud/datacenter IPs). "
                    "Add HARVESTER_PROXIES or run from a residential IP to continue."
                )
                break

            self.result.tasks_completed += 1
            if self.result.tasks_completed % 5 == 0 or found_here > 0:
                self.emit_progress(
                    f"[{idx:,}/{len(tasks):,}] YP '{term}' in {geo_str} -> +{found_here} new "
                    f"(total: +{self.result.new_domains_added:,})"
                )
            polite_sleep(base_delay)
