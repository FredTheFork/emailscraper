"""Unit tests for URL normalization, redirect unwrapping, domain blocking & ccTLD country mapping."""

from __future__ import annotations

import pytest

from window_harvester.domains import normalize_url, reverse_commoncrawl_host, unwrap_redirect_url


class TestDomainNormalization:
    def test_standard_urls_collapse_to_root_domain(self) -> None:
        r1 = normalize_url("https://www.safestyle-windows.co.uk/upvc-windows/casement/?utm_source=google")
        r2 = normalize_url("http://SAFESTYLE-WINDOWS.CO.UK:80/contact")
        r3 = normalize_url("safestyle-windows.co.uk")
        assert r1 is not None and r2 is not None and r3 is not None
        assert r1.domain == r2.domain == r3.domain == "safestyle-windows.co.uk"
        assert r1.canonical_url == "https://safestyle-windows.co.uk"
        assert r1.inferred_country == "GB"
        assert "/upvc-windows/casement/" in r1.original_path

    def test_wildcard_and_semicolon_entries_cleaned(self) -> None:
        ct = normalize_url("*.hertsdoubleglazing.co.uk")
        assert ct is not None
        assert ct.domain == "hertsdoubleglazing.co.uk"

        osm_multi = normalize_url("https://bristolglaziers.co.uk; https://facebook.com/bristolglaziers")
        assert osm_multi is not None
        assert osm_multi.domain == "bristolglaziers.co.uk"

    def test_international_idn_domain(self) -> None:
        res = normalize_url("https://www.müller-fensterbau.de/holzfenster")
        assert res is not None
        assert res.inferred_country == "DE"
        assert "fensterbau" in res.sld

    def test_unwrap_search_and_social_redirects(self) -> None:
        g_url = "https://www.google.com/url?q=https%3A%2F%2Facmewindows.co.uk%2Fhome&sa=U"
        assert unwrap_redirect_url(g_url) == "https://acmewindows.co.uk/home"
        norm = normalize_url(g_url)
        assert norm is not None and norm.domain == "acmewindows.co.uk"

        ddg_url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Ftimberwindows.com%2Fsash"
        norm_ddg = normalize_url(ddg_url)
        assert norm_ddg is not None and norm_ddg.domain == "timberwindows.com"

        fb_url = "https://l.facebook.com/l.php?u=https%3A%2F%2Flondonglaziers.co.uk"
        norm_fb = normalize_url(fb_url)
        assert norm_fb is not None and norm_fb.domain == "londonglaziers.co.uk"

    @pytest.mark.parametrize(
        "blocked_input",
        [
            "https://www.facebook.com/acmewindows",
            "https://www.instagram.com/acmewindows",
            "https://www.linkedin.com/company/acme-windows",
            "https://www.yell.com/biz/acme-windows-watford-12345/",
            "https://www.checkatrade.com/trades/acmewindows",
            "https://www.trustatrader.com/traders/acme-windows",
            "https://www.yelp.com/biz/acme-window-austin",
            "https://www.yelp.co.uk/biz/london-sash-windows",
            "https://www.yellowpages.com/austin-tx/mip/acme-windows-123",
            "https://www.houzz.co.uk/professionals/windows/acme",
            "https://www.microsoft.com/en-gb/windows",
            "https://blogs.windows.com/windowsexperience/",
            "https://www.windowscentral.com/software-apps/windows-11",
            "https://www.tenforums.com/tutorials/",
            "https://www.glassdoor.co.uk/Reviews/index.htm",
            "https://www.amazon.co.uk/dp/B00123",
            "https://www.screwfix.com/c/building-doors/windows",
            "https://www.homedepot.com/b/Doors-Windows",
            "https://en.wikipedia.org/wiki/Window",
            "https://www.gov.uk/building-regulations-approval",
            "https://planning.hertfordshire.gov.uk/windows",
            "https://physics.ox.ac.uk/glass",
            "https://acmewindows.blogspot.com",
            "https://acmewindows.wixsite.com/home",
            "https://www.specsavers.co.uk/glasses",
            "https://www.autoglass.co.uk/",
            "https://www.safelite.com/",
            "mailto:sales@acmewindows.co.uk",
            "tel:+441707123456",
            "http://192.168.1.10/windows",
            "",
        ],
    )
    def test_blocks_directories_social_tech_gov_and_invalid(self, blocked_input: str) -> None:
        assert normalize_url(blocked_input) is None

    def test_country_inference_handles_cctlds_and_generic_tlds(self) -> None:
        assert normalize_url("acmewindows.co.uk").inferred_country == "GB"  # type: ignore[union-attr]
        assert normalize_url("acmewindows.uk").inferred_country == "GB"  # type: ignore[union-attr]
        assert normalize_url("acmewindows.com.au").inferred_country == "AU"  # type: ignore[union-attr]
        assert normalize_url("acmewindows.co.nz").inferred_country == "NZ"  # type: ignore[union-attr]
        assert normalize_url("acmewindows.ca").inferred_country == "CA"  # type: ignore[union-attr]
        assert normalize_url("acmewindows.ie").inferred_country == "IE"  # type: ignore[union-attr]
        assert normalize_url("acmefenster.de").inferred_country == "DE"  # type: ignore[union-attr]
        assert normalize_url("acmekozijnen.nl").inferred_country == "NL"  # type: ignore[union-attr]
        # Generic TLDs should NOT invent a country
        assert normalize_url("acmewindows.com").inferred_country is None  # type: ignore[union-attr]
        assert normalize_url("acmewindows.co").inferred_country is None  # type: ignore[union-attr]
        assert normalize_url("apex.glass").inferred_country is None  # type: ignore[union-attr]

    def test_reverse_commoncrawl_host(self) -> None:
        assert reverse_commoncrawl_host("uk.co.safestyle-windows") == "safestyle-windows.co.uk"
        assert reverse_commoncrawl_host("com.andersenwindows") == "andersenwindows.com"
        assert reverse_commoncrawl_host("au.com.sydneyglaziers") == "sydneyglaziers.com.au"
