"""Official UK Companies House Harvester — Every Active UK Glazing & Window Company (Free Key).

Downloads every active registered UK company across all official fenestration & glass SIC codes:
  - 43342: Glazing (double glazing, window installation, glaziers)
  - 25120: Manufacture of doors and windows of metal (aluminium, steel, Crittall)
  - 22230: Manufacture of builders' ware of plastic (uPVC windows & extrusions)
  - 16230: Manufacture of other builders' carpentry and joinery (timber & sash windows)
  - 23110: Manufacture of flat glass
  - 23120: Shaping and processing of flat glass (toughened, laminated, sealed units)
  - 43320: Joinery installation (filtered to window/glazing/glass/conservatory company names)

Then resolves each company's official website URL via Serper, Brave API, or free `ddgs` search!
"""

from __future__ import annotations

import base64
import re
from typing import Any

from window_harvester.domains import normalize_url
from window_harvester.http_client import make_sync_client, polite_sleep, request_with_retry
from window_harvester.sources.base import BaseSource
from window_harvester.taxonomy import UK_COMPANIES_HOUSE_SIC_CODES

CH_ADVANCED_SEARCH_URL = "https://api.company-information.service.gov.uk/advanced-search/companies"
_BROAD_SIC_CODES: frozenset[str] = frozenset({"16230", "43320", "22230"})
_UK_WINDOW_NAME_RE = re.compile(
    r"\b(?:windows?|glaz\w+|glass|upvc|pvcu|sash|casement|bifold|bi-fold|crittall|fenestrat\w*"
    r"|skylight\w*|rooflight\w*|lantern\w*|conservator\w+|oranger\w+|frames?|curtain\s+wall\w*|sealed\s+unit\w*)\b",
    re.I,
)
_COMPANY_SUFFIX_RE = re.compile(r"\b(?:limited|ltd|plc|llp|uk|co|company|holdings|group)\b\.?", re.I)


def parse_companies_house_items(items: list[dict[str, Any]], sic_code: str, category: str) -> list[dict[str, str]]:
    """Extract clean active company queue rows from Companies House `/advanced-search/companies`."""
    out: list[dict[str, str]] = []
    filter_by_name = sic_code in _BROAD_SIC_CODES
    for item in items:
        if not isinstance(item, dict):
            continue
        cnum = str(item.get("company_number") or "").strip()
        cname = str(item.get("company_name") or "").strip()
        if not cnum or not cname:
            continue
        if filter_by_name and not _UK_WINDOW_NAME_RE.search(cname):
            continue
        addr = item.get("registered_office_address") if isinstance(item.get("registered_office_address"), dict) else {}
        out.append(
            {
                "company_id": f"GB:{cnum}",
                "company_name": cname,
                "country": "GB",
                "locality": str(addr.get("locality") or addr.get("region") or ""),
                "postcode": str(addr.get("postal_code") or ""),
                "sic_code": sic_code,
                "category": category,
            }
        )
    return out


def company_name_tokens(company_name: str) -> list[str]:
    cleaned = _COMPANY_SUFFIX_RE.sub(" ", company_name.lower())
    return [t for t in re.findall(r"[a-z0-9]{3,}", cleaned) if t not in ("the", "and", "services", "solutions")]


class CompaniesHouseSource(BaseSource):
    """Harvest all active UK glazing, window & flat-glass firms from Companies House + resolve URLs."""

    name = "companies_house"
    display_name = "UK Companies House Official Registry (Free API Key)"
    requires_api_key = True
    is_free = True
    estimated_yield = "15,000 – 45,000+ UK Company URLs"
    description = (
        "Downloads every active UK company in Glazing (43342), Metal Windows (25120), uPVC (22230), "
        "Timber Joinery (16230) & Flat Glass (23110/23120), then resolves official website URLs."
    )
    flush_size = 200

    def is_available(self) -> tuple[bool, str]:
        if self.config.companies_house_api_key:
            return (True, "ready")
        return (
            False,
            "Set free COMPANIES_HOUSE_API_KEY (https://developer.company-information.service.gov.uk)",
        )

    def _run_impl(self) -> None:
        if not self.config.companies_house_api_key:
            raise RuntimeError("COMPANIES_HOUSE_API_KEY is required.")

        # Phase 1: Pull all active UK window/glazing companies into `company_queue`
        auth = base64.b64encode(f"{self.config.companies_house_api_key}:".encode("utf-8")).decode("ascii")
        headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
        done = self.db.get_done_checkpoints(self.name)

        with make_sync_client(timeout=40.0, headers=headers) as client:
            for sic_code, (label, category) in UK_COMPANIES_HOUSE_SIC_CODES.items():
                cp_key = f"sic:{sic_code}"
                if cp_key in done:
                    continue
                self.emit_progress(f"Downloading UK Companies House SIC {sic_code}: {label}...")
                start_index = 0
                page_size = 1000
                queued_for_sic = 0

                while start_index < 10_000:  # CH API start_index window limit
                    params = {
                        "sic_codes": sic_code,
                        "company_status": "active",
                        "size": page_size,
                        "start_index": start_index,
                    }
                    try:
                        resp = request_with_retry(client, "GET", CH_ADVANCED_SEARCH_URL, params=params, max_retries=3)
                        if resp.status_code == 416 or resp.status_code == 404:
                            break
                        if resp.status_code != 200:
                            self.result.errors += 1
                            break
                        data = resp.json()
                    except Exception:
                        self.result.errors += 1
                        break

                    raw_items = data.get("items") or []
                    if not raw_items:
                        break
                    parsed = parse_companies_house_items(raw_items, sic_code, category)
                    queued_for_sic += self.db.enqueue_companies(parsed)
                    if len(raw_items) < page_size:
                        break
                    start_index += page_size
                    polite_sleep(0.55)  # CH limit is 600 req / 5 min (2 req/s)

                self.db.save_checkpoint(self.name, cp_key, items_found=queued_for_sic)
                self.emit_progress(f"SIC {sic_code}: queued {queued_for_sic:,} active UK window/glass firms")

        # Phase 2: Resolve queued company names to official website URLs
        self._resolve_company_websites()

    def _resolve_company_websites(self) -> None:
        while not self.should_stop():
            batch = self.db.fetch_pending_companies(country="GB", limit=200)
            if not batch:
                break
            for row in batch:
                if self.should_stop():
                    break
                cid = str(row["company_id"])
                cname = str(row["company_name"])
                locality = str(row["locality"] or "")
                postcode = str(row["postcode"] or "")
                category = str(row["category"] or "general_windows")

                query = f'"{cname}" {locality} UK official website'.strip()
                candidates = self._search_company_url(query)
                tokens = company_name_tokens(cname)
                matched_domain = None

                for url, title, snippet in candidates:
                    norm = normalize_url(url)
                    if norm is None:
                        continue
                    # Require at least one distinctive company name token in SLD or title
                    hay = f"{norm.sld} {title.lower()}"
                    if tokens and not any(tok in hay for tok in tokens[:3]):
                        continue
                    accepted = self.ingest_candidate(
                        url,
                        business_name=cname.title(),
                        title=title,
                        snippet=snippet,
                        category_hint=category,
                        source_trust="high",
                        country="GB",
                        city=locality,
                        postcode=postcode,
                        sample_query=f"companies_house:{cid}",
                    )
                    if accepted:
                        matched_domain = norm.domain
                        break

                self.db.mark_company_status(cid, "resolved" if matched_domain else "not_found", matched_domain)
                self.result.tasks_completed += 1
                if self.result.tasks_completed % 15 == 0:
                    self.flush()
                    self.emit_progress(
                        f"Resolved {self.result.tasks_completed:,} UK Companies House firms -> "
                        f"+{self.result.new_domains_added:,} new websites"
                    )

    def _search_company_url(self, query: str) -> list[tuple[str, str, str]]:
        """Use Serper -> Brave -> free DDGS (whichever is available) to look up a company's website."""
        if self.config.serper_api_key:
            with make_sync_client(
                timeout=20.0,
                headers={"X-API-KEY": self.config.serper_api_key, "Content-Type": "application/json"},
            ) as c:
                try:
                    r = c.post("https://google.serper.dev/search", json={"q": query, "gl": "gb", "num": 5})
                    if r.status_code == 200:
                        return [
                            (str(x.get("link", "")), str(x.get("title", "")), str(x.get("snippet", "")))
                            for x in (r.json().get("organic") or [])[:5]
                        ]
                except Exception:
                    return []

        if self.config.brave_api_key:
            with make_sync_client(
                timeout=20.0,
                headers={"X-Subscription-Token": self.config.brave_api_key, "Accept": "application/json"},
            ) as c:
                try:
                    r = c.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        params={"q": query, "country": "GB", "count": 5},
                    )
                    if r.status_code == 200:
                        web = r.json().get("web") or {}
                        return [
                            (str(x.get("url", "")), str(x.get("title", "")), str(x.get("description", "")))
                            for x in (web.get("results") or [])[:5]
                        ]
                except Exception:
                    return []

        # Free fallback via ddgs
        try:
            from ddgs import DDGS

            polite_sleep(max(1.2, self.config.request_delay))
            hits = DDGS(proxy=self.proxies.next(), timeout=12).text(
                query, region="uk-en", max_results=5, backend="auto"
            )
            return [(str(h.get("href", "")), str(h.get("title", "")), str(h.get("body", ""))) for h in hits]
        except Exception:
            return []
