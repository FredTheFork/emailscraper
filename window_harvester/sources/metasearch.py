"""Free Multi-Engine Search Harvester — DuckDuckGo, Brave, Google (Startpage), Bing (Yahoo) & Mojeek.

Sweeps the combinatorial `{window keyword} × {city / town / postcode}` matrix across
four distinct live search engine indexes simultaneously (Brave, Bing via DuckDuckGo/Yahoo,
Google via Startpage, and UK-based independent crawler Mojeek) with ZERO API keys required.
Supports rotating proxies, adaptive rate-limiting, pagination, and full SQLite checkpointing.
"""

from __future__ import annotations

from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

from window_harvester.geo import COUNTRY_TO_DDGS_REGION
from window_harvester.http_client import polite_sleep
from window_harvester.sources.base import BaseSource

_EXCLUDED_ENGINES: frozenset[str] = frozenset({"wikipedia", "grokipedia", "annasarchive"})


def detect_web_backends() -> str:
    """Inspect installed `ddgs` text engines and return comma-joined live web search backends."""
    try:
        from ddgs.engines import ENGINES

        text_engines = ENGINES.get("text", {})
        enabled = [
            name
            for name, cls in text_engines.items()
            if name not in _EXCLUDED_ENGINES and not getattr(cls, "disabled", False)
        ]
        if enabled:
            return ",".join(enabled)
    except Exception:
        pass
    return "auto"


class MetaSearchSource(BaseSource):
    """Combinatorial keyword × location web search across DuckDuckGo, Brave, Startpage, Yahoo & Mojeek."""

    name = "metasearch"
    display_name = "Multi-Engine Search (DDG + Brave + Google/Startpage + Bing/Yahoo + Mojeek)"
    requires_api_key = False
    is_free = True
    estimated_yield = "30,000 – 150,000+ URLs (resumable across sessions)"
    description = (
        "Free, zero-key combinatorial search across DuckDuckGo, Brave, Startpage (Google results), "
        "Yahoo (Bing results), and Mojeek over thousands of {keyword} × {city/postcode} queries."
    )
    flush_size = 200

    def _run_impl(self) -> None:
        tasks = self.build_search_matrix(include_trade_queries=True)
        done = self.db.get_done_checkpoints(self.name)
        backends = detect_web_backends()
        max_pages = max(1, min(self.config.max_pages_per_query, 5))
        base_delay = max(1.2, self.config.request_delay)
        consecutive_ratelimits = 0

        self.emit_progress(
            f"Prepared {len(tasks):,} search queries across backends [{backends}] "
            f"({len(done):,} already checkpointed)"
        )

        for idx, task in enumerate(tasks, start=1):
            if self.should_stop():
                break
            cp_key = task["key"]
            if cp_key in done:
                self.result.tasks_skipped_checkpoint += 1
                continue

            country = task["country"]
            region_code = COUNTRY_TO_DDGS_REGION.get(country, "us-en")
            query = task["query"]
            before_added = self.result.new_domains_added
            had_error = False

            for page in range(1, max_pages + 1):
                if self.should_stop():
                    break
                proxy = self.proxies.next()
                try:
                    ddgs_client = DDGS(proxy=proxy, timeout=15)
                    results = ddgs_client.text(
                        query,
                        region=region_code,
                        safesearch="moderate",
                        max_results=40,
                        page=page,
                        backend=backends,
                    )
                    consecutive_ratelimits = 0
                except RatelimitException:
                    consecutive_ratelimits += 1
                    had_error = True
                    self.result.errors += 1
                    cooldown = min(90.0, base_delay * (2 ** min(consecutive_ratelimits, 5)))
                    polite_sleep(cooldown)
                    break
                except (TimeoutException, DDGSException):
                    # "No results found." raises DDGSException on later pages — normal termination
                    break
                except Exception:
                    had_error = True
                    self.result.errors += 1
                    break

                if not results:
                    break

                for hit in results:
                    href = str(hit.get("href") or hit.get("url") or "").strip()
                    if not href:
                        continue
                    title = str(hit.get("title") or "")
                    body = str(hit.get("body") or hit.get("snippet") or "")
                    self.ingest_candidate(
                        href,
                        title=title,
                        snippet=body,
                        category_hint=task["keyword"],
                        source_trust="low",
                        country=country,
                        region=task.get("region") or None,
                        city=task.get("city") or None,
                        postcode=task.get("postcode") or None,
                        sample_query=query,
                    )

                if len(results) < 8:
                    break
                polite_sleep(base_delay * 0.8)

            self.flush()
            found_here = self.result.new_domains_added - before_added
            if not had_error or found_here > 0:
                self.db.save_checkpoint(self.name, cp_key, items_found=found_here)
            self.result.tasks_completed += 1

            if self.result.tasks_completed % 5 == 0 or found_here > 0:
                self.emit_progress(
                    f"[{idx:,}/{len(tasks):,}] '{query}' -> +{found_here} new "
                    f"(source total: +{self.result.new_domains_added:,})"
                )
            polite_sleep(base_delay)
