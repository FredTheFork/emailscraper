"""Trade Association & Seed Directory Outbound Harvester ($0, Zero API Keys).

Fetches public window/glass trade association member directories, exhibition exhibitor lists,
and any custom directory URLs provided via `--seed-file`, extracting every outbound external
business website link (`<a href="https://...">`) and running it through our deduplicator and
relevance classifier.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from window_harvester.domains import normalize_url
from window_harvester.http_client import make_sync_client, polite_sleep, random_headers, request_with_retry
from window_harvester.sources.base import BaseSource

# Curated public fenestration, glazing & glass trade association / exhibition member pages
DEFAULT_TRADE_SEED_PAGES: tuple[tuple[str, str, str], ...] = (
    ("https://www.ggf.org.uk/find-a-member/", "GB", "Glass and Glazing Federation"),
    ("https://www.bwf.org.uk/choose-wood/find-a-member/", "GB", "British Woodworking Federation"),
    ("https://www.cab-org.co.uk/members/", "GB", "Council for Aluminium in Building"),
    ("https://www.steel-window-association.co.uk/find-a-member/", "GB", "Steel Window Association"),
    ("https://www.nfrc.org/windows-doors-skylights/", "US", "National Fenestration Rating Council"),
    ("https://www.wdma.com/page/MemberDirectory", "US", "Window & Door Manufacturers Association"),
    ("https://www.glass.org/member-directory", "US", "National Glass Association"),
    ("https://fenestrationcanada.ca/member-directory/", "CA", "Fenestration Canada"),
    ("https://www.agwa.com.au/members", "AU", "Australian Glass and Window Association"),
    ("https://www.wganz.org.nz/find-a-member/", "NZ", "Window & Glass Association NZ"),
)


def extract_outbound_links(page_url: str, html: str) -> list[tuple[str, str]]:
    """Return deduplicated `(external_url, anchor_text)` pairs pointing outside `page_url`'s domain."""
    host_norm = normalize_url(page_url)
    host_domain = host_norm.domain if host_norm else ""

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    seen_domains: set[str] = set()
    out: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        raw_href = str(a["href"]).strip()
        if not raw_href or raw_href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full_url = urljoin(page_url, raw_href)
        norm = normalize_url(full_url)
        if norm is None or norm.domain == host_domain:
            continue
        if norm.domain in seen_domains:
            continue
        seen_domains.add(norm.domain)
        anchor = " ".join(a.get_text(" ", strip=True).split())[:200]
        title_attr = str(a.get("title") or "").strip()[:120]
        label = anchor or title_attr
        out.append((norm.canonical_url, label))
    return out


class SeedDirectoryCrawlerSource(BaseSource):
    """Extract outbound window business websites from trade association & custom directory pages."""

    name = "trade_directories"
    display_name = "Window Trade Associations & Custom Directory Crawler"
    requires_api_key = False
    is_free = True
    estimated_yield = "2,000 – 25,000+ high-trust trade member URLs"
    description = (
        "Crawls public window, timber, aluminium, steel & glass trade association directories "
        "(plus any custom directory URLs in --seed-file) and extracts every member company website."
    )
    flush_size = 200

    def _collect_seeds(self) -> list[tuple[str, str, str]]:
        seeds: list[tuple[str, str, str]] = []
        allowed = {c.upper() for c in self.config.countries} if self.config.countries else None
        for url, cc, label in DEFAULT_TRADE_SEED_PAGES:
            if allowed is None or cc in allowed:
                seeds.append((url, cc, label))
        for sf in self.config.seed_files:
            p = Path(sf)
            if not p.is_file():
                continue
            for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "," in line:
                    u, cc = [x.strip() for x in line.split(",", 1)]
                    seeds.append((u, cc.upper()[:2], p.name))
                else:
                    seeds.append((line, "", p.name))
        return seeds

    def _run_impl(self) -> None:
        seeds = self._collect_seeds()
        done = self.db.get_done_checkpoints(self.name)

        with make_sync_client(timeout=30.0, proxy=self.proxies.next(), headers=random_headers()) as client:
            for idx, (url, cc, label) in enumerate(seeds, start=1):
                if self.should_stop():
                    break
                cp_key = f"seed:{url}"
                if cp_key in done:
                    self.result.tasks_skipped_checkpoint += 1
                    continue

                before_added = self.result.new_domains_added
                try:
                    resp = request_with_retry(client, "GET", url, max_retries=2)
                    if resp.status_code != 200:
                        self.result.errors += 1
                        continue
                    for ext_url, anchor in extract_outbound_links(url, resp.text):
                        # Custom/trade directory pages explicitly list vetted window members
                        self.ingest_candidate(
                            ext_url,
                            business_name=anchor,
                            category_hint="window manufacturer supplier member",
                            source_trust="medium",
                            country=cc or None,
                            sample_query=f"trade_dir:{label}",
                        )
                    self.flush()
                    found_here = self.result.new_domains_added - before_added
                    self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
                    self.result.tasks_completed += 1
                    self.emit_progress(f"[{idx}/{len(seeds)}] {label}: +{found_here} member websites")
                except Exception:
                    self.result.errors += 1
                polite_sleep(max(0.8, self.config.request_delay))
