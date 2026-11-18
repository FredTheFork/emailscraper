"""Exhaustive precision & recall tests for the window/glazing/glass classifier."""

from __future__ import annotations

import pytest

from window_harvester.classifier import classify_candidate, classify_domain_only, classify_html
from window_harvester.models import FilterOptions


class TestDomainClassifier:
    @pytest.mark.parametrize(
        ("domain", "expected_cat"),
        [
            ("hertsdoubleglazing.co.uk", "double_triple_glazing"),
            ("nordictripleglazing.com", "double_triple_glazing"),
            ("london-secondary-glazing.co.uk", "double_triple_glazing"),
            ("upvcwindowsdirect.co.uk", "upvc_vinyl"),
            ("acme-vinyl-windows.com", "upvc_vinyl"),
            ("london-sash-windows.co.uk", "timber_wood"),
            ("bespoke-timber-windows.co.uk", "timber_wood"),
            ("oakwoodwindows.com", "timber_wood"),
            ("flush-casement-windows.co.uk", "timber_wood"),
            ("origin-aluminium-windows.co.uk", "aluminium"),
            ("miami-aluminum-windows.com", "aluminium"),
            ("surrey-bifold-doors.co.uk", "aluminium"),
            ("crittall-windows.com", "steel_crittall"),
            ("heritage-steel-windows.co.uk", "steel_crittall"),
            ("apex-curtain-walling.co.uk", "commercial_curtain_wall"),
            ("ukfenestration.co.uk", "commercial_curtain_wall"),
            ("architecturalglazing.co.uk", "commercial_curtain_wall"),
            ("tradewindowsuppliers.co.uk", "manufacturers_suppliers"),
            ("midland-window-fabricators.co.uk", "manufacturers_suppliers"),
            ("sealedunitmanufacturers.co.uk", "manufacturers_suppliers"),
            ("mueller-fensterbau.de", "manufacturers_suppliers"),
            ("texas-window-replacement.com", "installers_replacement"),
            ("florida-impact-windows.com", "installers_replacement"),
            ("premierwindowsanddoors.ca", "installers_replacement"),
            ("watfordglaziers.co.uk", "glass_glaziers"),
            ("toughenedglassuk.co.uk", "glass_glaziers"),
            ("sydneyglassandglazing.com.au", "glass_glaziers"),
            ("glaserei-schmidt.de", "glass_glaziers"),
            ("vitrerie-lyon.fr", "glass_glaziers"),
            ("amsterdam-kozijnen.nl", "installers_replacement"),
            ("rossi-serramenti.it", "installers_replacement"),
            ("cristaleria-madrid.es", "glass_glaziers"),
            ("okna-pvc-krakow.pl", "upvc_vinyl"),
            ("glarmester-hansen.dk", "glass_glaziers"),
            ("apexskylights.com", "skylights_conservatories"),
            ("uk-roof-lanterns.co.uk", "skylights_conservatories"),
            ("hertsconservatories.co.uk", "skylights_conservatories"),
            ("york-stained-glass.co.uk", "stained_decorative_glass"),
            ("anglianwindows.co.uk", "general_windows"),
            ("andersenwindows.com", "general_windows"),
            ("midlandglass.co.uk", "glass_glaziers"),
            ("architectural.glass", "glass_glaziers"),
        ],
    )
    def test_accepts_every_window_and_glass_vertical(self, domain: str, expected_cat: str) -> None:
        res = classify_domain_only(domain)
        assert res.accepted, f"Expected {domain} to be accepted, got rejected ({res.reason})"
        assert expected_cat in res.categories, f"Expected {expected_cat} in {res.categories} for {domain}"
        assert res.confidence >= 0.65

    @pytest.mark.parametrize(
        "noise_domain",
        [
            # Microsoft Windows OS / software / hosting / drivers / keys
            "windows11tips.com",
            "windows10download.com",
            "windows7drivers.net",
            "windowsxpforever.com",
            "windowsserverguide.com",
            "windowsupdatefixer.com",
            "windowsdefenderhelp.com",
            "windowskeyshop.com",
            "windowsvpshosting.com",
            "windowsrdp.com",
            "windowspasswordrecovery.com",
            "windowssoftwarehub.com",
            "windowsforum.de",
            "win11activator.com",
            "xwindowsystem.org",
            "tilingwindowmanager.com",
            "windowapp.io",
            # Eyewear & optics
            "cheapeyeglasses.com",
            "designersunglasses.co.uk",
            "readingglassesdirect.com",
            "londonopticians.co.uk",
            "cityglasses.co.uk",
            "bluelightglasses.com",
            # Drinkware, bottles, smoking glass, jewelry, lab glass, marine, phone
            "finewineglass.com",
            "craftbeerglass.co.uk",
            "cocktailglassware.com",
            "glassbottlesuk.co.uk",
            "headyglassbongs.com",
            "glasspipeshop.com",
            "seaglassjewelry.com",
            "muranoglassart.it",
            "labglassware.com",
            "iphoneglassrepair.com",
            "fiberglassboats.com",
            "fiberglasspools.com",
            "glassfiberoptics.com",
            "glassceilingproject.com",
            "hourglasscosmetics.com",
            # Non-building conservatories
            "bostonmusicconservatory.com",
            "royalconservatoryofdance.co.uk",
            "botanicconservatory.org",
            # Auto glass & window cleaning excluded by default
            "fastautoglass.com",
            "mobilewindshieldrepair.com",
            "ukwindscreens.co.uk",
            "sparklewindowcleaning.co.uk",
            "prowindowwashers.com",
            # Unrelated domains
            "joespizza.com",
            "smithaccountants.co.uk",
        ],
    )
    def test_rejects_ms_windows_eyewear_drinkware_auto_and_noise(self, noise_domain: str) -> None:
        res = classify_domain_only(noise_domain)
        assert not res.accepted, f"Expected noise domain {noise_domain} to be REJECTED, got {res}"

    def test_optional_subvertical_toggles_work(self) -> None:
        assert not classify_domain_only("sparklewindowcleaning.co.uk").accepted
        clean_res = classify_domain_only(
            "sparklewindowcleaning.co.uk",
            FilterOptions(include_window_cleaning=True),
        )
        assert clean_res.accepted and "window_cleaning" in clean_res.categories

        assert not classify_domain_only("fastautoglass.com").accepted
        auto_res = classify_domain_only("fastautoglass.com", FilterOptions(include_auto_glass=True))
        assert auto_res.accepted and "auto_glass" in auto_res.categories

        assert not classify_domain_only("londonblinds.co.uk").accepted
        treat_res = classify_domain_only("londonblinds.co.uk", FilterOptions(include_treatments=True))
        assert treat_res.accepted and "window_treatments" in treat_res.categories


class TestContextualAndHtmlClassifier:
    def test_accepts_brand_named_window_firms_with_context(self) -> None:
        # Domains without the word "window" in them!
        norm, res = classify_candidate(
            "https://origin-global.com",
            business_name="Origin Frames Ltd",
            title="Origin | Bespoke Aluminium Bi-Fold Doors & Windows Manufacturer UK",
            source_trust="low",
        )
        assert norm is not None and res.accepted
        assert "aluminium" in res.categories
        assert "manufacturers_suppliers" in res.categories

        norm2, res2 = classify_candidate(
            "https://smithandsonsjoinery.co.uk/sash-windows",
            category_hint="sash-windows",
            source_trust="medium",
        )
        assert norm2 is not None and norm2.domain == "smithandsonsjoinery.co.uk"
        assert res2.accepted
        assert "timber_wood" in res2.categories

    def test_rejects_tech_blog_mentioning_windows_11(self) -> None:
        _, res = classify_candidate(
            "https://superpctips.com/fix-windows-update",
            title="How to Fix Microsoft Windows 11 Update Error 0x8007",
            snippet="Download our free registry cleaner compatible with Windows 10 and Windows 11.",
            source_trust="low",
        )
        assert not res.accepted

    def test_html_classifier_verifies_real_glazier_and_detects_parked_and_os(self) -> None:
        real_html = """
        <html>
          <head>
            <title>Hertfordshire Double Glazing | uPVC, Timber Sash & Aluminium Windows</title>
            <meta name="description" content="FENSA registered installers of uPVC, aluminium and Crittall steel windows in Welwyn Garden City.">
          </head>
          <body><h1>Bespoke Windows & Doors</h1><p>Supply and installation of sealed units and roof lanterns.</p></body>
        </html>
        """
        cls, title, desc, is_parked = classify_html("https://hertsglaze.co.uk", real_html)
        assert cls.accepted and not is_parked
        assert "Hertfordshire Double Glazing" in title
        assert "FENSA" in desc
        assert {"double_triple_glazing", "upvc_vinyl", "timber_wood", "aluminium", "steel_crittall"}.issubset(
            set(cls.categories)
        )

        parked_html = """
        <html><head><title>coolwindows.com - This domain is for sale! | HugeDomains.com</title></head>
        <body><h1>Buy this domain today</h1></body></html>
        """
        p_cls, _, _, p_parked = classify_html("https://coolwindows.com", parked_html)
        assert not p_cls.accepted and p_parked

        ms_html = """
        <html><head><title>FastWin Tool - Free Download for Microsoft Windows 11 & Windows 10</title></head>
        <body><h1>Best Windows 11 Registry Optimizer & Driver Updater</h1></body></html>
        """
        m_cls, _, _, m_parked = classify_html("https://fastwintool.com", ms_html)
        assert not m_cls.accepted and not m_parked
