"""Playwright Google Maps Harvester — Direct Browser Google Maps Website Extractor ($0, No Key).

Drives a headless (or visible) Chromium instance over Google Maps search results for every
`{window keyword} × {city / town / postcode}` pair, automatically handling UK/EU cookie
consent banners, scrolling the results panel to the bottom (up to ~120 businesses per query),
and extracting every business's external website URL straight into the deduplicated DB.

Install browser once:
    pip install playwright && playwright install chromium
"""

from __future__ import annotations

from urllib.parse import quote_plus

from window_harvester.http_client import polite_sleep
from window_harvester.sources.base import BaseSource


class PlaywrightGoogleMapsSource(BaseSource):
    """Zero-API-key headless Chromium Google Maps feed scroller & website extractor."""

    name = "playwright_gmaps"
    display_name = "Google Maps Direct Browser Scraper (Playwright)"
    requires_api_key = False
    is_free = True
    estimated_yield = "50,000 – 250,000+ URLs (resumable across runs)"
    description = (
        "Scrolls Google Maps listings directly in headless Chromium across {keyword} × {city/postcode}, "
        "dismisses cookie banners, and extracts every business website URL ($0, no API key)."
    )
    flush_size = 100

    def is_available(self) -> tuple[bool, str]:
        try:
            import playwright  # noqa: F401

            return (True, "ready")
        except ImportError:
            return (
                False,
                "Install Playwright first: pip install playwright && playwright install chromium",
            )

    def _run_impl(self) -> None:
        from playwright.sync_api import sync_playwright

        tasks = self.build_search_matrix(include_trade_queries=False)
        done = self.db.get_done_checkpoints(self.name)
        max_scrolls = max(6, self.config.max_pages_per_query * 6)

        self.emit_progress(
            f"Google Maps browser grid: {len(tasks):,} location×keyword tasks ({len(done):,} checkpointed)"
        )

        with sync_playwright() as pw:
            proxy_url = self.proxies.next()
            launch_kwargs: dict[str, object] = {
                "headless": self.config.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            }
            if proxy_url:
                launch_kwargs["proxy"] = {"server": proxy_url}

            browser = pw.chromium.launch(**launch_kwargs)  # type: ignore[arg-type]
            context = browser.new_context(
                viewport={"width": 1366, "height": 900},
                locale="en-GB",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            # Block heavy map tiles, images & fonts for ~5x faster scrolling and tiny bandwidth
            context.route(
                "**/*.{png,jpg,jpeg,webp,gif,svg,woff,woff2,ttf,mp4}",
                lambda route: route.abort(),
            )
            page = context.new_page()
            consent_handled = False

            try:
                for idx, task in enumerate(tasks, start=1):
                    if self.should_stop():
                        break
                    cp_key = task["key"]
                    if cp_key in done:
                        self.result.tasks_skipped_checkpoint += 1
                        continue

                    query = task["query"]
                    maps_url = f"https://www.google.com/maps/search/{quote_plus(query)}?hl=en"
                    before_added = self.result.new_domains_added

                    try:
                        page.goto(maps_url, wait_until="domcontentloaded", timeout=30_000)

                        # Handle EU/UK GDPR consent interstitial once per session
                        if not consent_handled:
                            for btn_text in ("Reject all", "Accept all", "I agree"):
                                btn = page.locator(f"button:has-text('{btn_text}')").first
                                if btn.count() > 0 and btn.is_visible():
                                    btn.click(timeout=5_000)
                                    page.wait_for_load_state("domcontentloaded", timeout=15_000)
                                    consent_handled = True
                                    break

                        feed = page.locator("div[role='feed']").first
                        try:
                            feed.wait_for(state="attached", timeout=10_000)
                            # Scroll the side panel until end-of-list or max_scrolls
                            prev_count = 0
                            stagnant = 0
                            for _ in range(max_scrolls):
                                feed.evaluate("el => el.scrollBy(0, 2400)")
                                page.wait_for_timeout(850)
                                cards_count = page.locator("div[role='feed'] div[role='article']").count()
                                body_tail = feed.inner_text()[-250:].lower()
                                if "reached the end of the list" in body_tail:
                                    break
                                if cards_count == prev_count:
                                    stagnant += 1
                                    if stagnant >= 3:
                                        break
                                else:
                                    stagnant = 0
                                    prev_count = cards_count
                        except Exception:
                            # Single direct place page opened instead of list feed
                            pass

                        # Extract all visible website anchors + associated card business names
                        extracted = page.evaluate(
                            """() => {
                                const results = [];
                                const seen = new Set();
                                // 1. Feed cards with direct Website button
                                document.querySelectorAll("div[role='article'], div.Nv2PK").forEach(card => {
                                    const web = card.querySelector("a[data-value='Website'], a[aria-label*='website' i]");
                                    if (!web || !web.href) return;
                                    if (seen.has(web.href)) return;
                                    seen.add(web.href);
                                    const titleEl = card.querySelector("div.qBF1Pd, a.hfpxzc");
                                    const name = titleEl
                                        ? (titleEl.textContent || titleEl.getAttribute("aria-label") || "").trim()
                                        : "";
                                    results.push({ url: web.href, name });
                                });
                                // 2. Single-place detail panel fallback
                                const singleWeb = document.querySelector("a[data-item-id='authority']");
                                if (singleWeb && singleWeb.href && !seen.has(singleWeb.href)) {
                                    const h1 = document.querySelector("h1");
                                    results.push({ url: singleWeb.href, name: h1 ? h1.textContent.trim() : "" });
                                }
                                return results;
                            }"""
                        )

                        for entry in extracted or []:
                            href = str(entry.get("url") or "").strip()
                            bname = str(entry.get("name") or "").strip()
                            if not href or "google." in href.lower() and "/url?" not in href.lower():
                                continue
                            self.ingest_candidate(
                                href,
                                business_name=bname,
                                category_hint=task["keyword"],
                                source_trust="medium",
                                country=task["country"],
                                region=task.get("region") or None,
                                city=task.get("city") or None,
                                postcode=task.get("postcode") or None,
                                sample_query=f"gmaps:{query}",
                            )

                        self.flush()
                        found_here = self.result.new_domains_added - before_added
                        self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
                        self.result.tasks_completed += 1
                        self.emit_progress(
                            f"[{idx:,}/{len(tasks):,}] GMaps '{query}' -> +{found_here} new "
                            f"(total: +{self.result.new_domains_added:,})"
                        )
                    except Exception:
                        self.result.errors += 1

                    polite_sleep(max(1.0, self.config.request_delay))
            finally:
                context.close()
                browser.close()
