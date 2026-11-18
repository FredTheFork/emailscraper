"""Base class shared by all website discovery harvesters."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from window_harvester.classifier import classify_candidate, classify_domain_only
from window_harvester.config import HarvestConfig
from window_harvester.db import HarvestDB
from window_harvester.domains import normalize_url
from window_harvester.http_client import ProxyRotator
from window_harvester.models import CandidateRecord, GeoLocation, SourceRunResult
from window_harvester.taxonomy import TRADE_AND_MANUFACTURER_QUERIES, get_keywords_for_country
from window_harvester.geo import get_locations

ProgressCallback = Callable[[str, str, SourceRunResult], None]


class BaseSource(ABC):
    """Abstract website discovery source with buffering, classification & checkpointing."""

    name: str = "base"
    display_name: str = "Base Source"
    requires_api_key: bool = False
    is_free: bool = True
    estimated_yield: str = ""
    description: str = ""
    flush_size: int = 500

    def __init__(
        self,
        db: HarvestDB,
        config: HarvestConfig,
        *,
        on_progress: ProgressCallback | None = None,
        stop_check: Callable[[], bool] | None = None,
    ) -> None:
        self.db = db
        self.config = config
        self.on_progress = on_progress
        self._external_stop = stop_check
        self.proxies = ProxyRotator(config.proxies)
        self.result = SourceRunResult(source=self.name)
        self._buffer: list[CandidateRecord] = []
        self._start_time = 0.0

    def is_available(self) -> tuple[bool, str]:
        """Return `(ready, reason)` — override in API-key sources."""
        return (True, "ready")

    def should_stop(self) -> bool:
        """Check whether user interrupted, max tasks hit, or target domain count reached."""
        if self._external_stop and self._external_stop():
            return True
        if (
            self.config.max_tasks_per_source is not None
            and self.result.tasks_completed >= self.config.max_tasks_per_source
        ):
            return True
        if self.config.target_domains is not None:
            if self.db.count_domains(active_only=True) >= self.config.target_domains:
                return True
        return False

    def ingest_domain_only(
        self,
        raw_domain_or_url: str,
        *,
        sample_query: str | None = None,
        country_hint: str | None = None,
    ) -> bool:
        """Classify & buffer a bare domain (for Common Crawl domain graph & CT logs)."""
        self.result.candidates_seen += 1
        norm = normalize_url(raw_domain_or_url)
        if norm is None:
            self.result.rejected_count += 1
            return False

        cls = classify_domain_only(norm, self.config.filters)
        if not cls.accepted:
            self.result.rejected_count += 1
            return False

        cc = norm.inferred_country or (country_hint.upper() if country_hint else None)
        if self.config.filters.allowed_countries and cc and cc not in self.config.filters.allowed_countries:
            self.result.rejected_count += 1
            return False

        self._buffer.append(
            CandidateRecord(
                url=norm.canonical_url,
                domain=norm.domain,
                source=self.name,
                confidence=cls.confidence,
                categories=cls.categories,
                country=cc,
                sample_query=sample_query,
            )
        )
        if len(self._buffer) >= self.flush_size:
            self.flush()
        return True

    def ingest_candidate(
        self,
        url: str,
        *,
        business_name: str = "",
        title: str = "",
        snippet: str = "",
        category_hint: str = "",
        source_trust: str = "medium",
        country: str | None = None,
        region: str | None = None,
        city: str | None = None,
        postcode: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        sample_query: str | None = None,
    ) -> bool:
        """Classify & buffer a contextual business website candidate (Maps, OSM, Overture, SERP, YP)."""
        self.result.candidates_seen += 1
        norm, cls = classify_candidate(
            url,
            business_name=business_name,
            title=title,
            snippet=snippet,
            category_hint=category_hint,
            source_trust=source_trust,
            options=self.config.filters,
        )
        if norm is None or not cls.accepted:
            self.result.rejected_count += 1
            return False

        resolved_country = (country.upper()[:2] if country and len(country.strip()) == 2 else None) or norm.inferred_country
        if (
            self.config.filters.allowed_countries
            and resolved_country
            and resolved_country not in self.config.filters.allowed_countries
        ):
            self.result.rejected_count += 1
            return False

        self._buffer.append(
            CandidateRecord(
                url=norm.canonical_url,
                domain=norm.domain,
                source=self.name,
                confidence=cls.confidence,
                categories=cls.categories,
                business_name=(business_name.strip()[:200] if business_name else None),
                country=resolved_country,
                region=(region.strip()[:120] if region else None),
                city=(city.strip()[:120] if city else None),
                postcode=(postcode.strip()[:32] if postcode else None),
                address=(address.strip()[:300] if address else None),
                phone=(phone.strip()[:64] if phone else None),
                lat=lat,
                lon=lon,
                sample_query=(sample_query[:200] if sample_query else None),
                page_title=(title.strip()[:300] if title else None),
                meta_description=(snippet.strip()[:500] if snippet else None),
            )
        )
        if len(self._buffer) >= self.flush_size:
            self.flush()
        return True

    def flush(self) -> tuple[int, int]:
        """Write buffered records into SQLite and update counters."""
        if not self._buffer:
            return (0, 0)
        batch = self._buffer
        self._buffer = []
        added, merged = self.db.upsert_batch(batch)
        self.result.new_domains_added += added
        self.result.existing_domains_merged += merged
        return (added, merged)

    def emit_progress(self, status_msg: str) -> None:
        self.result.elapsed_seconds = round(time.monotonic() - self._start_time, 1)
        if self.on_progress:
            self.on_progress(self.name, status_msg, self.result)

    def build_search_matrix(self, *, include_trade_queries: bool = True) -> list[dict[str, Any]]:
        """Build an interleaved `{keyword} × {location}` query plan across target countries.

        Interleaves Tier-1 keywords across all cities BEFORE moving to Tier-2/Tier-3 keywords,
        maximizing unique new websites discovered per minute right from the start!
        """
        target_ccs = self.config.countries or self.config.search_countries
        locations = get_locations(
            target_ccs,
            max_tier=self.config.geo_tier,
            include_uk_postcodes=self.config.include_uk_postcodes,
            include_uk_postcode_districts=self.config.include_uk_postcode_districts,
            custom_file=self.config.custom_locations_file,
        )

        # Group locations by country
        locs_by_cc: dict[str, list[GeoLocation]] = {}
        for loc in locations:
            locs_by_cc.setdefault(loc.country, []).append(loc)

        tasks: list[dict[str, Any]] = []

        # 1. High-yield nationwide B2B manufacturer / accreditation queries first
        if include_trade_queries and not self.config.custom_keywords:
            for cc in locs_by_cc:
                for q in TRADE_AND_MANUFACTURER_QUERIES.get(cc, ()):
                    tasks.append(
                        {
                            "key": f"trade:{cc}:{q.lower()}",
                            "query": q,
                            "keyword": q,
                            "country": cc,
                            "region": "",
                            "city": "",
                            "is_trade": True,
                        }
                    )

        # 2. Breadth-first keyword index sweep across all locations so every city gets
        #    hit with top keywords ("double glazing", "window installation", "uPVC windows", ...)
        #    before diving into deeper specialist keywords.
        kw_by_cc: dict[str, list[str]] = {
            cc: get_keywords_for_country(
                cc,
                max_tier=self.config.keyword_tier,
                include_treatments=self.config.filters.include_treatments,
                include_window_cleaning=self.config.filters.include_window_cleaning,
                include_auto_glass=self.config.filters.include_auto_glass,
                custom_keywords=self.config.custom_keywords,
            )
            for cc in locs_by_cc
        }
        max_kw_len = max((len(v) for v in kw_by_cc.values()), default=0)

        for kw_idx in range(max_kw_len):
            for cc, cc_locs in locs_by_cc.items():
                kws = kw_by_cc[cc]
                if kw_idx >= len(kws):
                    continue
                kw = kws[kw_idx]
                for loc in cc_locs:
                    q = f"{kw} {loc.search_label}"
                    tasks.append(
                        {
                            "key": f"{cc}:{loc.name.lower()}:{loc.region.lower()}:{kw.lower()}",
                            "query": q,
                            "keyword": kw,
                            "country": cc,
                            "region": loc.region,
                            "city": loc.name if loc.region != "UK Postcode" else "",
                            "postcode": loc.name if loc.region == "UK Postcode" else "",
                            "lat": loc.lat,
                            "lon": loc.lon,
                            "is_trade": False,
                        }
                    )

        return tasks

    def run(self) -> SourceRunResult:
        """Execute this harvester, guarantee final buffer flush, and return run metrics."""
        self._start_time = time.monotonic()
        try:
            self._run_impl()
        finally:
            self.flush()
            self.result.elapsed_seconds = round(time.monotonic() - self._start_time, 2)
        return self.result

    @abstractmethod
    def _run_impl(self) -> None:
        """Harvester-specific implementation."""
