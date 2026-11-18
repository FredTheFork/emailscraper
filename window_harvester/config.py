"""Configuration loader, API key discovery, proxy rotation list, and harvest presets."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from window_harvester.models import FilterOptions

ENGLISH_COUNTRIES: list[str] = ["GB", "US", "CA", "AU", "IE", "NZ", "ZA"]
GLOBAL_COUNTRIES: list[str] = [
    "GB", "US", "CA", "AU", "IE", "NZ", "ZA",
    "DE", "FR", "NL", "BE", "AT", "CH", "ES", "IT", "PT", "PL",
    "SE", "NO", "DK", "FI", "CZ", "RO", "HU", "GR",
    "AE", "SG", "IN", "MX", "BR",
]


@dataclass(slots=True)
class PresetSpec:
    """Definition of a named one-command harvest preset."""

    name: str
    description: str
    estimated_yield: str
    requires_api_keys: str
    base_sources: list[str]
    auto_api_sources: bool
    countries: list[str] | None  # None = all countries worldwide (for Overture/CC/OSM)
    search_countries: list[str]
    keyword_tier: int
    geo_tier: int
    include_uk_postcodes: bool = False


PRESETS: dict[str, PresetSpec] = {
    "free-fast": PresetSpec(
        name="free-fast",
        description="Fastest 100% free bulk harvest (Overture 60M POIs + Common Crawl 100M Domains + OSM 50 countries + CT SSL logs). Zero search rate limits; ideal first run in Google Colab.",
        estimated_yield="120,000 – 280,000+ unique URLs",
        requires_api_keys="None ($0)",
        base_sources=["overture", "osm", "crtsh", "commoncrawl_domains"],
        auto_api_sources=False,
        countries=None,
        search_countries=ENGLISH_COUNTRIES,
        keyword_tier=1,
        geo_tier=1,
    ),
    "free-max": PresetSpec(
        name="free-max",
        description="Every 100% free source combined: Overture Maps + Common Crawl Domains + Common Crawl CDX service pages + OpenStreetMap + CT Logs + Multi-Engine Search (DDG/Brave/Startpage-Google/Yahoo-Bing/Mojeek) + YellowPages.",
        estimated_yield="180,000 – 380,000+ unique URLs",
        requires_api_keys="None ($0)",
        base_sources=[
            "overture",
            "osm",
            "crtsh",
            "commoncrawl_domains",
            "commoncrawl_cdx",
            "yellowpages",
            "metasearch",
        ],
        auto_api_sources=False,
        countries=None,
        search_countries=GLOBAL_COUNTRIES,
        keyword_tier=2,
        geo_tier=2,
        include_uk_postcodes=True,
    ),
    "uk-complete": PresetSpec(
        name="uk-complete",
        description="Exhaustive UK sweep: every double glazing, uPVC, timber, sash, aluminium, steel/Crittall, skylight, conservatory, supplier & glazier across 350+ UK towns/boroughs + all 121 UK postcode areas + Companies House SICs.",
        estimated_yield="25,000 – 65,000+ UK window URLs",
        requires_api_keys="None required (auto-uses Serper/Google/Brave/Companies House if set)",
        base_sources=["overture", "osm", "crtsh", "commoncrawl_domains", "commoncrawl_cdx"],
        auto_api_sources=True,
        countries=["GB"],
        search_countries=["GB"],
        keyword_tier=3,
        geo_tier=3,
        include_uk_postcodes=True,
    ),
    "us-complete": PresetSpec(
        name="us-complete",
        description="Exhaustive US sweep across all 50 states (500+ cities): Overture + OSM + CT + Common Crawl + YellowPages + Google Maps/Search/Brave/DDG.",
        estimated_yield="80,000 – 200,000+ US window URLs",
        requires_api_keys="None required (auto-uses Serper/Google/Brave/DataForSEO if set)",
        base_sources=["overture", "osm", "crtsh", "commoncrawl_domains", "commoncrawl_cdx", "yellowpages"],
        auto_api_sources=True,
        countries=["US"],
        search_countries=["US"],
        keyword_tier=3,
        geo_tier=2,
    ),
    "english-world": PresetSpec(
        name="english-world",
        description="Full English-speaking world sweep (UK, US, Canada, Australia, Ireland, New Zealand, South Africa) across all free datasets + configured Maps/Search APIs.",
        estimated_yield="150,000 – 320,000+ unique URLs",
        requires_api_keys="None required (auto-uses any configured API keys)",
        base_sources=["overture", "osm", "crtsh", "commoncrawl_domains", "commoncrawl_cdx", "yellowpages"],
        auto_api_sources=True,
        countries=ENGLISH_COUNTRIES,
        search_countries=ENGLISH_COUNTRIES,
        keyword_tier=2,
        geo_tier=2,
        include_uk_postcodes=True,
    ),
    "maps-blitz": PresetSpec(
        name="maps-blitz",
        description="High-precision Maps-only sweep: Overture Maps + OpenStreetMap + Google Maps (Serper Maps / Google Places Quadtree / DataForSEO / SerpApi / Playwright).",
        estimated_yield="120,000 – 400,000+ verified local business URLs",
        requires_api_keys="Optional (SERPER_API_KEY or GOOGLE_PLACES_API_KEY recommended)",
        base_sources=["overture", "osm"],
        auto_api_sources=True,
        countries=None,
        search_countries=GLOBAL_COUNTRIES,
        keyword_tier=2,
        geo_tier=2,
        include_uk_postcodes=True,
    ),
    "global-500k": PresetSpec(
        name="global-500k",
        description="Maximum planet-wide harvest across 30+ countries & 15+ languages combining every bulk dataset, directory, CT log, and configured Google Maps / Google / Bing / Brave / DuckDuckGo harvester.",
        estimated_yield="300,000 – 600,000+ unique URLs",
        requires_api_keys="None required; adding SERPER_API_KEY / GOOGLE_PLACES_API_KEY / BRAVE_API_KEY pushes past 500k fastest",
        base_sources=[
            "overture",
            "osm",
            "crtsh",
            "commoncrawl_domains",
            "commoncrawl_cdx",
            "yellowpages",
        ],
        auto_api_sources=True,
        countries=None,
        search_countries=GLOBAL_COUNTRIES,
        keyword_tier=3,
        geo_tier=3,
        include_uk_postcodes=True,
    ),
}


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal zero-dependency `.env` loader (does not overwrite already-set env vars)."""
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key and key not in os.environ and val:
            os.environ[key] = val


@dataclass(slots=True)
class HarvestConfig:
    """Runtime settings shared across all harvester sources."""

    db_path: Path = field(default_factory=lambda: Path("data/window_websites.db"))
    output_dir: Path = field(default_factory=lambda: Path("output"))

    # Geographic & taxonomy scope
    countries: list[str] | None = None          # None = unrestricted global for bulk datasets
    search_countries: list[str] = field(default_factory=lambda: list(ENGLISH_COUNTRIES))
    keyword_tier: int = 2                       # 1..3
    geo_tier: int = 2                           # 1..3
    include_uk_postcodes: bool = False
    include_uk_postcode_districts: bool = False
    custom_keywords: list[str] | None = None
    custom_locations_file: str | None = None
    seed_files: list[str] = field(default_factory=list)

    # Limits & pacing
    target_domains: int | None = None           # Stop automatically once DB hits this count
    max_tasks_per_source: int | None = None     # Cap queries per source (useful for budget control / testing)
    max_pages_per_query: int = 3                # Search/Maps pagination depth
    concurrency: int = 10                       # API/HTTP concurrency
    request_delay: float = 1.0                  # Base delay (s) for rate-sensitive free scrapers
    headless: bool = True                       # For Playwright Chromium

    # Dataset overrides
    overture_release: str | None = None
    overture_s3_path: str | None = None
    commoncrawl_webgraph_url: str | None = None
    commoncrawl_max_domains_scan: int | None = None  # None = scan entire ~100M domain graph
    commoncrawl_cdx_max_pages: int = 5

    # Filtering rules
    filters: FilterOptions = field(default_factory=FilterOptions)

    # Optional API credentials
    serper_api_key: str = ""
    google_places_api_key: str = ""
    brave_api_key: str = ""
    serpapi_api_key: str = ""
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    companies_house_api_key: str = ""

    # Proxy rotation pool
    proxies: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls, dotenv_path: str | Path = ".env") -> HarvestConfig:
        load_dotenv(dotenv_path)
        proxies: list[str] = []
        raw_proxies = os.environ.get("HARVESTER_PROXIES", "").strip()
        if raw_proxies:
            proxies.extend(p.strip() for p in raw_proxies.split(",") if p.strip())
        proxy_file = os.environ.get("HARVESTER_PROXY_FILE", "").strip()
        if proxy_file and Path(proxy_file).is_file():
            for line in Path(proxy_file).read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    proxies.append(s)

        return cls(
            db_path=Path(os.environ.get("HARVESTER_DB_PATH", "data/window_websites.db")),
            output_dir=Path(os.environ.get("HARVESTER_OUTPUT_DIR", "output")),
            serper_api_key=os.environ.get("SERPER_API_KEY", "").strip(),
            google_places_api_key=os.environ.get("GOOGLE_PLACES_API_KEY", "").strip(),
            brave_api_key=os.environ.get("BRAVE_API_KEY", "").strip(),
            serpapi_api_key=os.environ.get("SERPAPI_API_KEY", "").strip(),
            dataforseo_login=os.environ.get("DATAFORSEO_LOGIN", "").strip(),
            dataforseo_password=os.environ.get("DATAFORSEO_PASSWORD", "").strip(),
            companies_house_api_key=os.environ.get("COMPANIES_HOUSE_API_KEY", "").strip(),
            proxies=proxies,
        )

    def configured_api_sources(self, *, maps_only: bool = False) -> list[str]:
        """Return API harvester names whose credentials are currently populated."""
        available: list[str] = []
        if self.serper_api_key:
            available.append("serper_maps" if maps_only else "serper")
        if self.google_places_api_key:
            available.append("google_places")
        if self.dataforseo_login and self.dataforseo_password:
            available.append("dataforseo")
        if self.serpapi_api_key:
            available.append("serpapi")
        if not maps_only:
            if self.brave_api_key:
                available.append("brave_api")
            if self.companies_house_api_key and (not self.countries or "GB" in self.countries):
                available.append("companies_house")
        return available

    def resolve_preset_sources(self, preset_name: str) -> list[str]:
        """Expand a preset into an ordered list of sources, auto-attaching configured APIs."""
        spec = PRESETS[preset_name]
        sources = list(spec.base_sources)
        if spec.auto_api_sources:
            maps_only = preset_name == "maps-blitz"
            api_srcs = self.configured_api_sources(maps_only=maps_only)
            for s in api_srcs:
                if s not in sources:
                    sources.append(s)
            # If no paid search API key is set, automatically fall back to free metasearch!
            has_paid_search = any(
                s in sources for s in ("serper", "serper_maps", "google_places", "dataforseo", "serpapi", "brave_api")
            )
            if not has_paid_search and not maps_only and "metasearch" not in sources:
                sources.append("metasearch")
        return sources
