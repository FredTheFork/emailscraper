"""OpenStreetMap Overpass Harvester — Global Glazier, Window Maker & Glass POI Sweep ($0).

Queries public Overpass API mirrors country-by-country across 50+ countries for every
business tagged `craft=glazier`, `craft=window_construction`, `shop=glaziery`,
`shop=windows`, `industrial=glass`, or carrying window/glazing/fenestration names with
website tags. Extracts clean external website URLs + name, city, postcode, phone & GPS.
"""

from __future__ import annotations

from typing import Any

from window_harvester.geo import OSM_COUNTRIES_PRIORITY
from window_harvester.http_client import make_sync_client, polite_sleep
from window_harvester.sources.base import BaseSource

OVERPASS_MIRRORS: tuple[str, ...] = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)

_WEBSITE_TAG_KEYS: tuple[str, ...] = (
    "website",
    "contact:website",
    "url",
    "contact:url",
    "website:en",
)

_NAME_REGEX = (
    "window|glaz|upvc|pvcu|fenestrat|skylight|sash|crittall|conservator"
    "|fenster|glaserei|glashandel|vitrer|miroiter|menuiserie|kozijn|glaszetter|dubbelglas"
    "|serrament|infissi|vetrer|ventana|cristaler|okna|szklarz|stolarka|caixilhar|esquadria"
    "|vidracar|vinduer|glarmester|fönster|fonster|ikkuna"
)


def build_overpass_query(country_iso2: str, *, include_treatments: bool = False) -> str:
    """Build an Overpass QL query for all window, glazing & glass businesses in a country."""
    cc = country_iso2.upper()
    shop_tags = "glaziery|windows|window_blind" if include_treatments else "glaziery|windows"
    return f"""
[out:json][timeout:180];
area["ISO3166-1"="{cc}"][admin_level=2]->.searchArea;
(
  nwr["craft"~"^(glazier|window_construction)$"](area.searchArea);
  nwr["shop"~"^({shop_tags})$"](area.searchArea);
  nwr["shop"="doors"]["name"~"{_NAME_REGEX}",i](area.searchArea);
  nwr["industrial"~"^(glass|windows)$"](area.searchArea);
  nwr["product"~"^(windows|glass|glazing|flat_glass|uPVC)$",i](area.searchArea);
  nwr["craft"]["name"~"{_NAME_REGEX}",i]["website"](area.searchArea);
  nwr["craft"]["name"~"{_NAME_REGEX}",i]["contact:website"](area.searchArea);
  nwr["office"="company"]["name"~"{_NAME_REGEX}",i]["website"](area.searchArea);
  nwr["office"="company"]["name"~"{_NAME_REGEX}",i]["contact:website"](area.searchArea);
  nwr["shop"]["name"~"{_NAME_REGEX}",i]["website"](area.searchArea);
  nwr["man_made"="works"]["name"~"{_NAME_REGEX}",i]["website"](area.searchArea);
);
out center tags;
""".strip()


def parse_overpass_elements(elements: list[dict[str, Any]], country: str) -> list[dict[str, Any]]:
    """Extract normalized business dicts from an Overpass API JSON `elements` list."""
    extracted: list[dict[str, Any]] = []
    for el in elements:
        tags = el.get("tags")
        if not isinstance(tags, dict):
            continue
        website = ""
        for k in _WEBSITE_TAG_KEYS:
            val = tags.get(k)
            if val and isinstance(val, str) and "." in val:
                website = val.strip()
                break
        if not website:
            continue

        craft = tags.get("craft", "")
        shop = tags.get("shop", "")
        industrial = tags.get("industrial", "")
        cat_hint = craft or shop or industrial or tags.get("product", "") or "window_business"
        is_direct_tag = craft in ("glazier", "window_construction") or shop in ("glaziery", "windows")

        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None and isinstance(el.get("center"), dict):
            lat = el["center"].get("lat")
            lon = el["center"].get("lon")

        street = tags.get("addr:street", "")
        houseno = tags.get("addr:housenumber", "")
        city = tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:suburb") or ""
        postcode = tags.get("addr:postcode", "")
        region = tags.get("addr:state") or tags.get("addr:county") or tags.get("addr:province") or ""
        phone = tags.get("phone") or tags.get("contact:phone") or ""
        address = " ".join(p for p in (houseno, street, city, postcode) if p).strip()

        extracted.append(
            {
                "url": website,
                "business_name": str(tags.get("name") or tags.get("brand") or ""),
                "category_hint": str(cat_hint),
                "source_trust": "high" if is_direct_tag else "medium",
                "country": country.upper(),
                "region": str(region),
                "city": str(city),
                "postcode": str(postcode),
                "address": address,
                "phone": str(phone),
                "lat": float(lat) if lat is not None else None,
                "lon": float(lon) if lon is not None else None,
            }
        )
    return extracted


class OpenStreetMapSource(BaseSource):
    """Harvest verified window makers, glaziers & glass shops globally from OpenStreetMap."""

    name = "osm"
    display_name = "OpenStreetMap Global Overpass Sweep"
    requires_api_key = False
    is_free = True
    estimated_yield = "20,000 – 55,000+ URLs"
    description = (
        "Sweeps 50 countries on OpenStreetMap for craft=glazier, craft=window_construction, "
        "shop=glaziery, shop=windows, and window/glazing manufacturers & contractors ($0, no API key)."
    )

    def _run_impl(self) -> None:
        countries = [c.upper() for c in self.config.countries] if self.config.countries else list(OSM_COUNTRIES_PRIORITY)
        done = self.db.get_done_checkpoints(self.name)

        headers = {
            "User-Agent": "WindowWebsiteHarvester/1.0 (OpenStreetMap research client)",
            "Accept": "application/json",
        }

        with make_sync_client(timeout=190.0, headers=headers) as client:
            for idx, cc in enumerate(countries, start=1):
                if self.should_stop():
                    break
                cp_key = f"country:{cc}"
                if cp_key in done:
                    self.result.tasks_skipped_checkpoint += 1
                    continue

                self.emit_progress(f"[{idx}/{len(countries)}] Querying OpenStreetMap for {cc}...")
                query = build_overpass_query(cc, include_treatments=self.config.filters.include_treatments)
                payload = self._query_mirrors(client, query, mirror_offset=idx - 1)
                if payload is None:
                    self.result.errors += 1
                    polite_sleep(4.0)
                    continue

                before_added = self.result.new_domains_added
                items = parse_overpass_elements(payload.get("elements", []), cc)
                for item in items:
                    self.ingest_candidate(
                        item["url"],
                        business_name=item["business_name"],
                        category_hint=item["category_hint"],
                        source_trust=item["source_trust"],
                        country=item["country"],
                        region=item["region"],
                        city=item["city"],
                        postcode=item["postcode"],
                        address=item["address"],
                        phone=item["phone"],
                        lat=item["lat"],
                        lon=item["lon"],
                        sample_query=f"osm:{cc}:{item['category_hint']}",
                    )

                self.flush()
                found_here = self.result.new_domains_added - before_added
                self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
                self.result.tasks_completed += 1
                self.emit_progress(
                    f"[{idx}/{len(countries)}] OSM {cc}: {len(items):,} tagged businesses -> "
                    f"+{found_here:,} new domains (total: +{self.result.new_domains_added:,})"
                )
                # Respect Overpass public mirror fair-use spacing
                polite_sleep(max(2.5, self.config.request_delay * 2.0))

    def _query_mirrors(self, client: Any, query: str, mirror_offset: int = 0) -> dict[str, Any] | None:
        """Try public Overpass mirrors in order until one returns valid JSON."""
        for attempt in range(len(OVERPASS_MIRRORS)):
            mirror = OVERPASS_MIRRORS[(mirror_offset + attempt) % len(OVERPASS_MIRRORS)]
            try:
                resp = client.post(mirror, data={"data": query})
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "elements" in data:
                        return data
                elif resp.status_code in (429, 504):
                    polite_sleep(5.0 * (attempt + 1))
            except Exception:
                polite_sleep(3.0 * (attempt + 1))
        return None
