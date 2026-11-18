"""Registry of all window website discovery sources."""

from __future__ import annotations

from window_harvester.sources.base import BaseSource
from window_harvester.sources.brave_api import BraveAPISource
from window_harvester.sources.commoncrawl_cdx import CommonCrawlCDXSource
from window_harvester.sources.commoncrawl_domains import CommonCrawlDomainsSource
from window_harvester.sources.companies_house import CompaniesHouseSource
from window_harvester.sources.crtsh import CrtShSource
from window_harvester.sources.dataforseo import DataForSEOSource
from window_harvester.sources.google_places import GooglePlacesQuadtreeSource
from window_harvester.sources.metasearch import MetaSearchSource
from window_harvester.sources.osm import OpenStreetMapSource
from window_harvester.sources.overture import OvertureSource
from window_harvester.sources.playwright_gmaps import PlaywrightGoogleMapsSource
from window_harvester.sources.seed_crawler import SeedDirectoryCrawlerSource
from window_harvester.sources.serpapi import SerpApiSource
from window_harvester.sources.serper import SerperCombinedSource, SerperMapsSource
from window_harvester.sources.yellowpages import YellowPagesSource

SOURCE_REGISTRY: dict[str, type[BaseSource]] = {
    # Tier 1 — 100% Free, Zero API Keys
    "overture": OvertureSource,
    "commoncrawl_domains": CommonCrawlDomainsSource,
    "commoncrawl_cdx": CommonCrawlCDXSource,
    "osm": OpenStreetMapSource,
    "crtsh": CrtShSource,
    "metasearch": MetaSearchSource,
    "yellowpages": YellowPagesSource,
    "playwright_gmaps": PlaywrightGoogleMapsSource,
    "trade_directories": SeedDirectoryCrawlerSource,
    # Tier 2 — Free Official Registry Key
    "companies_house": CompaniesHouseSource,
    # Tier 3 — High-Throughput Maps & Search Engine APIs
    "serper": SerperCombinedSource,
    "serper_maps": SerperMapsSource,
    "google_places": GooglePlacesQuadtreeSource,
    "brave_api": BraveAPISource,
    "serpapi": SerpApiSource,
    "dataforseo": DataForSEOSource,
}

# Friendly aliases so users can type `--sources ddg,gmaps,brave,cc` effortlessly
SOURCE_ALIASES: dict[str, str] = {
    "ddg": "metasearch",
    "duckduckgo": "metasearch",
    "bing": "metasearch",
    "startpage": "metasearch",
    "mojeek": "metasearch",
    "brave": "brave_api",
    "gmaps": "playwright_gmaps",
    "google_maps": "google_places",
    "places": "google_places",
    "cc": "commoncrawl_domains",
    "commoncrawl": "commoncrawl_domains",
    "cdx": "commoncrawl_cdx",
    "ct": "crtsh",
    "openstreetmap": "osm",
    "overpass": "osm",
    "yp": "yellowpages",
    "ch": "companies_house",
    "seeds": "trade_directories",
}


def resolve_source_name(name: str) -> str:
    slug = name.strip().lower().replace("-", "_")
    slug = SOURCE_ALIASES.get(slug, slug)
    if slug not in SOURCE_REGISTRY:
        valid = ", ".join(SOURCE_REGISTRY.keys())
        raise ValueError(f"Unknown source '{name}'. Available sources: {valid}")
    return slug


__all__ = [
    "BaseSource",
    "SOURCE_REGISTRY",
    "SOURCE_ALIASES",
    "resolve_source_name",
]
