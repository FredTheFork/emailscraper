"""Common Crawl CDX Index Harvester — Finds Non-Keyword Domains via Service-Page URLs.

Many window companies have brand domains without the word "window" or "glass" in them
(e.g. `origin-global.com`, `anglianhome.co.uk`, `smithjoinery.co.uk`, `apexremodeling.com`),
but their websites contain service pages like `/double-glazing`, `/upvc-windows`,
`/sash-windows`, `/aluminium-windows`, `/window-replacement`, `/curtain-walling`, etc.
This harvester queries Common Crawl's free public CDX JSON API across every target TLD to
capture all of those domains and normalize them to clean root URLs.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from window_harvester.http_client import make_sync_client, polite_sleep, request_with_retry
from window_harvester.sources.base import BaseSource
from window_harvester.taxonomy import build_cdx_patterns

CC_COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"


def fetch_latest_cdx_endpoint(client: Any) -> tuple[str, str]:
    """Return `(crawl_id, cdx_api_url)` for the newest Common Crawl index."""
    resp = request_with_retry(client, "GET", CC_COLLINFO_URL, max_retries=3)
    resp.raise_for_status()
    items = resp.json()
    if not isinstance(items, list) or not items:
        raise RuntimeError("Empty collinfo.json from Common Crawl")
    top = items[0]
    return str(top["id"]), str(top["cdx-api"])


def parse_cdx_jsonl(body: str) -> list[str]:
    """Parse newline-delimited JSON objects returned by Common Crawl CDX API."""
    urls: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        u = obj.get("url")
        status = str(obj.get("status", "200"))
        if u and status.startswith(("2", "3")):
            urls.append(str(u))
    return urls


class CommonCrawlCDXSource(BaseSource):
    """Query Common Crawl CDX index for window/glazing service pages across global TLDs."""

    name = "commoncrawl_cdx"
    display_name = "Common Crawl CDX Service-Page Index"
    requires_api_key = False
    is_free = True
    estimated_yield = "30,000 – 120,000+ URLs"
    description = (
        "Queries Common Crawl's free CDX index for /double-glazing, /upvc-windows, /timber-windows, "
        "/aluminium-windows, /window-replacement, etc. across global TLDs to find brand-named companies."
    )
    flush_size = 500

    def _run_impl(self) -> None:
        patterns = build_cdx_patterns(self.config.countries)
        done = self.db.get_done_checkpoints(self.name)
        max_pages = max(1, self.config.commoncrawl_cdx_max_pages)

        with make_sync_client(timeout=45.0, proxy=self.proxies.next()) as client:
            crawl_id, cdx_api = fetch_latest_cdx_endpoint(client)
            self.emit_progress(f"Using Common Crawl index {crawl_id} ({len(patterns)} URL patterns)")

            for idx, (pattern, cc_hint) in enumerate(patterns, start=1):
                if self.should_stop():
                    break
                cp_key = f"{crawl_id}:{pattern}"
                if cp_key in done:
                    self.result.tasks_skipped_checkpoint += 1
                    continue

                before_added = self.result.new_domains_added
                encoded_url = quote(pattern, safe="*:/.-_")

                try:
                    # Query total page count first so we never request out-of-range pages
                    num_url = (
                        f"{cdx_api}?url={encoded_url}&output=json"
                        f"&filter==status:200&filter==mime:text/html&showNumPages=true"
                    )
                    num_resp = request_with_retry(client, "GET", num_url, max_retries=2, backoff_base=2.0)
                    total_pages = 1
                    if num_resp.status_code == 200:
                        try:
                            info = json.loads(num_resp.text.strip().splitlines()[0])
                            total_pages = int(info.get("pages", 0))
                        except Exception:
                            total_pages = 1
                    elif num_resp.status_code == 404:
                        total_pages = 0

                    pages_to_fetch = min(total_pages, max_pages)
                    for page in range(pages_to_fetch):
                        if self.should_stop():
                            break
                        page_url = (
                            f"{cdx_api}?url={encoded_url}&output=json&fl=url,status"
                            f"&filter==status:200&filter==mime:text/html&page={page}"
                        )
                        resp = request_with_retry(client, "GET", page_url, max_retries=3, backoff_base=2.5)
                        if resp.status_code == 404:
                            break
                        if resp.status_code != 200:
                            self.result.errors += 1
                            break

                        for found_url in parse_cdx_jsonl(resp.text):
                            self.ingest_candidate(
                                found_url,
                                category_hint=pattern.split("/", 1)[-1].rstrip("*"),
                                source_trust="medium",
                                country=cc_hint or None,
                                sample_query=f"cdx:{pattern}",
                            )
                        polite_sleep(max(0.6, self.config.request_delay * 0.7))

                    self.flush()
                    found_here = self.result.new_domains_added - before_added
                    self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
                    self.result.tasks_completed += 1
                    self.emit_progress(
                        f"[{idx}/{len(patterns)}] {pattern} -> +{found_here:,} new "
                        f"(source total: +{self.result.new_domains_added:,})"
                    )
                except Exception:
                    self.result.errors += 1
                    polite_sleep(3.0)
