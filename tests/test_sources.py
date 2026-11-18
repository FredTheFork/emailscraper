"""Comprehensive tests for all harvester sources, SQL builders, quadtree tiling & parsers."""

from __future__ import annotations

import gzip
from pathlib import Path

import duckdb

from window_harvester.config import HarvestConfig
from window_harvester.db import HarvestDB
from window_harvester.geo import generate_country_grid, get_locations
from window_harvester.models import BoundingBox
from window_harvester.sources.brave_api import parse_brave_web_response
from window_harvester.sources.commoncrawl_cdx import parse_cdx_jsonl
from window_harvester.sources.commoncrawl_domains import CommonCrawlDomainsSource
from window_harvester.sources.companies_house import parse_companies_house_items
from window_harvester.sources.crtsh import extract_domains_from_crtsh_json
from window_harvester.sources.dataforseo import parse_dataforseo_response
from window_harvester.sources.google_places import parse_google_places_response
from window_harvester.sources.metasearch import detect_web_backends
from window_harvester.sources.osm import build_overpass_query, parse_overpass_elements
from window_harvester.sources.overture import OvertureSource
from window_harvester.sources.seed_crawler import extract_outbound_links
from window_harvester.sources.serpapi import parse_serpapi_response
from window_harvester.sources.serper import parse_serper_maps_response, parse_serper_search_response
from window_harvester.sources.yellowpages import parse_yellowpages_html
from window_harvester.taxonomy import build_cdx_patterns, get_keywords_for_country


def test_overture_source_end_to_end_on_real_parquet(tmp_path: Path) -> None:
    """Create a real Overture-schema Parquet file with DuckDB and run OvertureSource against it."""
    pq_file = tmp_path / "places.parquet"
    con = duckdb.connect(":memory:")
    con.execute(
        f"""
        COPY (
            SELECT * FROM (VALUES
                (
                    ['https://www.hertssashwindows.co.uk/home'],
                    {{'primary': 'Herts Sash Windows Ltd'}},
                    {{'primary': 'windows_installation', 'alternate': ['carpenter']}},
                    [{{'country': 'GB', 'region': 'Hertfordshire', 'locality': 'Welwyn Garden City', 'postcode': 'AL8 6AB', 'freeform': '12 High St'}}],
                    ['+441707000111'],
                    {{'xmin': -0.21, 'xmax': -0.20, 'ymin': 51.80, 'ymax': 51.81}},
                    0.92,
                    'open'
                ),
                (
                    ['https://smithjoinery.co.uk'],
                    {{'primary': 'Smith Timber Windows & Doors'}},
                    {{'primary': 'contractor', 'alternate': ['home_improvement']}},
                    [{{'country': 'GB', 'region': 'Kent', 'locality': 'Maidstone', 'postcode': 'ME14', 'freeform': '5 Mill Rd'}}],
                    ['+441622000222'],
                    {{'xmin': 0.52, 'xmax': 0.53, 'ymin': 51.27, 'ymax': 51.28}},
                    0.85,
                    'open'
                ),
                (
                    ['https://pella.com'],
                    {{'primary': 'Pella Windows & Doors of Austin'}},
                    {{'primary': 'door_and_window', 'alternate': []}},
                    [{{'country': 'US', 'region': 'TX', 'locality': 'Austin', 'postcode': '78701', 'freeform': '100 Congress Ave'}}],
                    ['+15125550199'],
                    {{'xmin': -97.74, 'xmax': -97.73, 'ymin': 30.26, 'ymax': 30.27}},
                    0.95,
                    'open'
                ),
                (
                    ['https://fastautoglass.com'],
                    {{'primary': 'Fast Auto Glass & Windshield'}},
                    {{'primary': 'auto_glass_service', 'alternate': []}},
                    [{{'country': 'US', 'region': 'TX', 'locality': 'Dallas', 'postcode': '75201', 'freeform': '1 Main St'}}],
                    ['+12145550100'],
                    {{'xmin': -96.80, 'xmax': -96.79, 'ymin': 32.77, 'ymax': 32.78}},
                    0.95,
                    'open'
                ),
                (
                    ['https://cityopticians.co.uk'],
                    {{'primary': 'City Glasses & Opticians'}},
                    {{'primary': 'eyewear_and_opticians', 'alternate': []}},
                    [{{'country': 'GB', 'region': 'London', 'locality': 'London', 'postcode': 'EC1', 'freeform': '9 Fleet St'}}],
                    ['+442070001111'],
                    {{'xmin': -0.11, 'xmax': -0.10, 'ymin': 51.51, 'ymax': 51.52}},
                    0.95,
                    'open'
                ),
                (
                    ['https://closedglazing.co.uk'],
                    {{'primary': 'Closed Double Glazing'}},
                    {{'primary': 'glazier', 'alternate': []}},
                    [{{'country': 'GB', 'region': 'Essex', 'locality': 'Chelmsford', 'postcode': 'CM1', 'freeform': '2 Park Rd'}}],
                    [],
                    {{'xmin': 0.47, 'xmax': 0.48, 'ymin': 51.73, 'ymax': 51.74}},
                    0.90,
                    'closed'
                ),
                (
                    ['https://www.facebook.com/someglazier'],
                    {{'primary': 'FB Only Glazier'}},
                    {{'primary': 'glazier', 'alternate': []}},
                    [{{'country': 'GB', 'region': 'Surrey', 'locality': 'Woking', 'postcode': 'GU21', 'freeform': '3 Oak Ln'}}],
                    [],
                    {{'xmin': -0.56, 'xmax': -0.55, 'ymin': 51.31, 'ymax': 51.32}},
                    0.88,
                    'open'
                )
            ) AS t(websites, names, categories, addresses, phones, bbox, confidence, operating_status)
        ) TO '{pq_file}' (FORMAT PARQUET);
        """
    )
    con.close()

    cfg = HarvestConfig(db_path=tmp_path / "ov.db", overture_s3_path=str(pq_file))
    with HarvestDB(cfg.db_path) as db:
        res = OvertureSource(db, cfg).run()
        assert res.new_domains_added == 3
        domains = {r["domain"] for r in db.iter_domains()}
        assert domains == {"hertssashwindows.co.uk", "smithjoinery.co.uk", "pella.com"}

        # Re-running hits checkpoint and skips cleanly
        res2 = OvertureSource(db, cfg).run()
        assert res2.tasks_skipped_checkpoint == 1
        assert res2.new_domains_added == 0


def test_commoncrawl_domains_stream_on_gzip_file(tmp_path: Path) -> None:
    gz_path = tmp_path / "cc-domain-ranks.txt.gz"
    lines = [
        "#pos\tval\tpr_pos\tpr_val\thost_rev\tn_hosts",
        "1\t10.0\t1\t9.9\tcom.microsoft\t5000",
        "2\t8.1\t2\t8.0\tcom.windows11tips\t1",
        "3\t7.5\t3\t7.4\tuk.co.safestyle-windows\t3",
        "4\t7.2\t4\t7.1\tuk.co.hertsdoubleglazing\t1",
        "5\t7.0\t5\t6.9\tcom.crittall-windows\t2",
        "6\t6.8\t6\t6.7\tde.mueller-fensterbau\t1",
        "7\t6.5\t7\t6.4\tau.com.sydneyaluminiumwindows\t1",
        "8\t6.1\t8\t6.0\tcom.cheapeyeglasses\t1",
        "9\t6.0\t9\t5.9\tcom.fastautoglass\t1",
        "10\t5.9\t10\t5.8\tuk.co.sparklewindowcleaning\t1",
        "11\t5.5\t11\t5.4\tcom.joespizzashop\t1",
    ]
    with gzip.open(gz_path, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    cfg = HarvestConfig(db_path=tmp_path / "cc.db", commoncrawl_webgraph_url=str(gz_path))
    with HarvestDB(cfg.db_path) as db:
        res = CommonCrawlDomainsSource(db, cfg).run()
        assert res.new_domains_added == 5
        found = {r["domain"] for r in db.iter_domains()}
        assert found == {
            "safestyle-windows.co.uk",
            "hertsdoubleglazing.co.uk",
            "crittall-windows.com",
            "mueller-fensterbau.de",
            "sydneyaluminiumwindows.com.au",
        }


def test_parsers_across_osm_crtsh_cdx_yp_serper_places_brave_serpapi_dfs_ch_seeds() -> None:
    # 1. OpenStreetMap Overpass
    q = build_overpass_query("GB")
    assert 'ISO3166-1"="GB"' in q and "window_construction" in q
    osm_items = parse_overpass_elements(
        [
            {
                "type": "node",
                "lat": 51.75,
                "lon": -0.33,
                "tags": {
                    "name": "St Albans Glaziers",
                    "craft": "glazier",
                    "contact:website": "https://stalbansglaziers.co.uk",
                    "addr:city": "St Albans",
                    "addr:postcode": "AL1 3AA",
                    "phone": "+44 1727 000000",
                },
            }
        ],
        "GB",
    )
    assert len(osm_items) == 1 and osm_items[0]["source_trust"] == "high"

    # 2. crt.sh
    ct_hosts = extract_domains_from_crtsh_json(
        [
            {"common_name": "*.watfordglazing.co.uk", "name_value": "*.watfordglazing.co.uk\nwatfordglazing.co.uk"},
            {"common_name": "info@ignore.co.uk", "name_value": "sashwindowsuk.co.uk"},
        ]
    )
    assert ct_hosts == ["watfordglazing.co.uk", "sashwindowsuk.co.uk"]

    # 3. Common Crawl CDX
    cdx_urls = parse_cdx_jsonl(
        '{"url": "https://apexjoinery.co.uk/timber-windows", "status": "200"}\n'
        '{"url": "https://deadsite.co.uk/timber-windows", "status": "404"}\n'
    )
    assert cdx_urls == ["https://apexjoinery.co.uk/timber-windows"]

    # 4. YellowPages HTML + JSON-LD
    yp_html = """
    <html><body>
      <div class="result">
        <a class="business-name">Lone Star Vinyl Windows</a>
        <div class="categories"><a>Windows</a><a>Glaziers</a></div>
        <div class="phones phone primary">(512) 555-1234</div>
        <div class="street-address">500 Lamar Blvd</div>
        <div class="locality">Austin, TX 78703</div>
        <a class="track-visit-website" href="https://lonestarvinylwindows.com">Website</a>
      </div>
      <a class="next ajax-page" href="/search?page=2">Next</a>
    </body></html>
    """
    yp_items, has_next = parse_yellowpages_html(yp_html, "Austin", "TX")
    assert has_next and len(yp_items) == 1
    assert yp_items[0]["url"] == "https://lonestarvinylwindows.com"
    assert yp_items[0]["postcode"] == "78703"

    # 5. Serper Maps + Organic
    sm = parse_serper_maps_response(
        {"places": [{"title": "Kent uPVC Ltd", "website": "https://kentupvc.co.uk", "type": "Window supplier", "latitude": 51.2, "longitude": 0.5}]}
    )
    assert len(sm) == 1 and sm[0]["url"] == "https://kentupvc.co.uk"
    so = parse_serper_search_response(
        {"organic": [{"title": "Trade Aluminium Windows", "link": "https://tradeali.co.uk", "snippet": "AluK fabricator"}]}
    )
    assert len(so) == 1 and so[0]["url"] == "https://tradeali.co.uk"

    # 6. Google Places v1 + Quadtree BoundingBox split
    gp_items, raw_cnt, tok = parse_google_places_response(
        {
            "places": [
                {
                    "displayName": {"text": "Leeds Steel Windows"},
                    "websiteUri": "https://leedssteelwindows.co.uk",
                    "primaryType": "general_contractor",
                    "formattedAddress": "Leeds LS1, UK",
                    "location": {"latitude": 53.8, "longitude": -1.55},
                },
                {"displayName": {"text": "No Website Installer"}},
            ],
            "nextPageToken": "abc123",
        }
    )
    assert len(gp_items) == 1 and raw_cnt == 2 and tok == "abc123"
    box = BoundingBox(51.0, -1.0, 52.0, 0.0, "GB", "london", 0)
    children = box.subdivide()
    assert len(children) == 4 and all(c.depth == 1 for c in children)
    assert box.approx_width_km > 50

    # 7. Brave API, SerpApi, DataForSEO
    br = parse_brave_web_response({"web": {"results": [{"url": "https://bristolwindows.co.uk", "title": "Bristol Windows", "description": "Double glazing"}]}})
    assert len(br) == 1
    sp = parse_serpapi_response({"local_results": [{"title": "Celtic Glazing", "website": "https://celticglazing.ie", "type": "Glazier"}]})
    assert len(sp) == 1
    dfs = parse_dataforseo_response(
        {"tasks": [{"result": [{"items": [{"type": "maps_search", "title": "Melbourne Glass", "url": "https://melbourneglass.com.au", "category": "Glazier"}]}]}]}
    )
    assert len(dfs) == 1

    # 8. UK Companies House SIC filtering
    ch_43342 = parse_companies_house_items(
        [{"company_number": "12345678", "company_name": "SMITH & SONS LTD", "registered_office_address": {"locality": "Watford", "postal_code": "WD17"}}],
        "43342",
        "double_triple_glazing",
    )
    assert len(ch_43342) == 1  # Dedicated glazing SIC keeps even brand-named firms!
    ch_43320 = parse_companies_house_items(
        [
            {"company_number": "11111111", "company_name": "OAK KITCHEN CABINETS LTD"},
            {"company_number": "22222222", "company_name": "HERITAGE SASH WINDOWS LTD"},
        ],
        "43320",
        "timber_wood",
    )
    assert len(ch_43320) == 1 and ch_43320[0]["company_id"] == "GB:22222222"

    # 9. Seed Directory Outbound Extractor
    dir_html = """
    <html><body>
      <a href="/about">Internal</a>
      <a href="https://facebook.com/ggf">Social Blocked</a>
      <a href="https://www.crittall-windows.com/products">Crittall Windows Ltd</a>
      <a href="https://www.crittall-windows.com/contact">Duplicate Domain</a>
      <a href="https://www.pilkington.com/en-gb/uk">Pilkington UK</a>
    </body></html>
    """
    outbound = extract_outbound_links("https://www.steel-window-association.co.uk/members", dir_html)
    assert [u for u, _ in outbound] == ["https://crittall-windows.com", "https://pilkington.com"]

    # 10. MetaSearch active backends exclude wikipedia/grokipedia
    backends = detect_web_backends()
    assert "wikipedia" not in backends and "grokipedia" not in backends
    assert "duckduckgo" in backends


def test_geo_and_taxonomy_scale() -> None:
    uk_locs = get_locations(["GB"], max_tier=3, include_uk_postcodes=True)
    us_locs = get_locations(["US"], max_tier=2)
    assert len(uk_locs) >= 450
    assert len(us_locs) >= 450

    uk_kws = get_keywords_for_country("GB", max_tier=3)
    us_kws = get_keywords_for_country("US", max_tier=3)
    de_kws = get_keywords_for_country("DE", max_tier=2)
    assert len(uk_kws) >= 70
    assert len(us_kws) >= 65
    assert "Fensterbau" in de_kws

    # Over 60,000+ queries across GB + US alone before even adding UK postcode districts!
    assert (len(uk_locs) * len(uk_kws) + len(us_locs) * len(us_kws)) > 60_000
    assert len(build_cdx_patterns(["GB", "US", "AU", "DE", "FR", "NL", "PL"])) > 150
    assert len(generate_country_grid("GB")) == 80


def test_google_places_adaptive_quadtree_subdivides_saturated_tiles(tmp_path: Path, monkeypatch) -> None:
    """Prove that a tile hitting Google's 60-result cap automatically splits into 4 child tiles."""
    from window_harvester.sources import google_places as gp_mod

    visited_boxes: list[str] = []

    def fake_search_box(self, _client, keyword: str, box: BoundingBox):
        visited_boxes.append(box.label)
        if box.depth == 0:
            # Simulate saturated metro tile (60 results -> triggers 4-way quadtree split!)
            self.ingest_candidate(
                "https://londonrootglazing.co.uk",
                business_name="London Root Glazing",
                category_hint=keyword,
                country="GB",
            )
            return (60, 1, True)
        # Child quadrant returns 10 results (below saturation -> stops splitting)
        slug = box.label.lower().replace(":", "").replace("-", "")
        self.ingest_candidate(
            f"https://{slug}windows.co.uk",
            business_name=f"{box.label} Windows Ltd",
            category_hint=keyword,
            country="GB",
        )
        return (10, 1, True)

    monkeypatch.setattr(gp_mod, "generate_country_grid", lambda _cc: [BoundingBox(51.3, -0.5, 51.7, 0.3, "GB", "london", 0)])
    monkeypatch.setattr(gp_mod.GooglePlacesQuadtreeSource, "_search_box", fake_search_box)

    cfg = HarvestConfig(
        db_path=tmp_path / "qt.db",
        countries=["GB"],
        custom_keywords=["double glazing"],
        google_places_api_key="test-key",
    )
    with HarvestDB(cfg.db_path) as db:
        res = gp_mod.GooglePlacesQuadtreeSource(db, cfg).run()
        # 1 root tile + 4 subdivided child tiles (NW, NE, SW, SE) = 5 tiles & 5 unique window sites!
        assert res.tasks_completed == 5
        assert res.new_domains_added == 5
        assert set(visited_boxes) == {"london", "london:NW", "london:NE", "london:SW", "london:SE"}

