"""Certificate Transparency (`crt.sh`) Harvester — Active HTTPS Window Business Domains ($0).

Every modern business website registers a public TLS/SSL certificate logged into global
Certificate Transparency logs. Querying `crt.sh` across ~150 surgical window, double-glazing,
uPVC, timber, sash, aluminium, steel, Crittall, glazier, fenestration, skylight & European
patterns uncovers tens of thousands of active — including brand-new — window business sites.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from window_harvester.http_client import make_sync_client, polite_sleep, request_with_retry
from window_harvester.sources.base import BaseSource
from window_harvester.taxonomy import CRTSH_PATTERNS

CRTSH_BASE_URL = "https://crt.sh/"


def extract_domains_from_crtsh_json(entries: list[dict[str, Any]]) -> list[str]:
    """Deduplicate all certificate CN and SAN DNS names returned by `crt.sh/?output=json`."""
    seen: set[str] = set()
    out: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        for field in ("common_name", "name_value"):
            raw = item.get(field)
            if not raw or not isinstance(raw, str):
                continue
            for line in raw.splitlines():
                host = line.strip().lower().removeprefix("*.")
                if not host or "@" in host or " " in host or "." not in host:
                    continue
                if host not in seen:
                    seen.add(host)
                    out.append(host)
    return out


class CrtShSource(BaseSource):
    """Discover SSL-enabled window, glazing & glass domains via Certificate Transparency logs."""

    name = "crtsh"
    display_name = "Certificate Transparency SSL Logs (crt.sh)"
    requires_api_key = False
    is_free = True
    estimated_yield = "30,000 – 90,000+ URLs"
    description = (
        "Queries global Certificate Transparency logs (crt.sh) for non-expired HTTPS certificates "
        "across 150+ double glazing, uPVC, timber, aluminium, steel, glazier & window patterns ($0)."
    )
    flush_size = 800

    def _select_patterns(self) -> list[str]:
        patterns = list(CRTSH_PATTERNS)
        if not self.config.countries:
            return patterns
        # Keep country-matching TLD patterns + universal keyword stems
        ccs = {c.upper() for c in self.config.countries}
        tld_map = {
            ".co.uk": "GB",
            ".uk": "GB",
            ".ie": "IE",
            ".com.au": "AU",
            ".co.nz": "NZ",
            ".ca": "CA",
            ".co.za": "ZA",
            ".us": "US",
            ".dk": "DK",
            ".no": "NO",
        }
        filtered: list[str] = []
        for p in patterns:
            matched_tld_cc = None
            for tld, cc in tld_map.items():
                if p.endswith(tld):
                    matched_tld_cc = cc
                    break
            if matched_tld_cc is None or matched_tld_cc in ccs:
                filtered.append(p)
        return filtered

    def _run_impl(self) -> None:
        patterns = self._select_patterns()
        done = self.db.get_done_checkpoints(self.name)

        headers = {
            "User-Agent": "WindowWebsiteHarvester/1.0",
            "Accept": "application/json",
        }

        with make_sync_client(timeout=65.0, headers=headers, proxy=self.proxies.next()) as client:
            for idx, pattern in enumerate(patterns, start=1):
                if self.should_stop():
                    break
                cp_key = f"ct:{pattern}"
                if cp_key in done:
                    self.result.tasks_skipped_checkpoint += 1
                    continue

                url = f"{CRTSH_BASE_URL}?q={quote(pattern, safe='')}&output=json&exclude=expired"
                before_added = self.result.new_domains_added
                try:
                    resp = request_with_retry(client, "GET", url, max_retries=2, backoff_base=3.0)
                    if resp.status_code != 200:
                        self.result.errors += 1
                        polite_sleep(4.0)
                        continue
                    data = resp.json()
                    if not isinstance(data, list):
                        data = []

                    hosts = extract_domains_from_crtsh_json(data)
                    for host in hosts:
                        self.ingest_domain_only(host, sample_query=f"crtsh:{pattern}")

                    self.flush()
                    found_here = self.result.new_domains_added - before_added
                    self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
                    self.result.tasks_completed += 1
                    self.emit_progress(
                        f"[{idx}/{len(patterns)}] crt.sh {pattern}: {len(hosts):,} certs -> "
                        f"+{found_here:,} new domains (total: +{self.result.new_domains_added:,})"
                    )
                except Exception:
                    # Broad patterns occasionally hit crt.sh DB statement timeout; log and move on
                    self.result.errors += 1
                polite_sleep(max(1.8, self.config.request_delay * 1.5))
