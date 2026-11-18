"""Tests for SQLite deduplication/merging, checkpoints, company queue, and chunked exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from window_harvester.db import HarvestDB
from window_harvester.exporter import export_websites
from window_harvester.models import CandidateRecord, VerifyStatus
from window_harvester.pipeline import import_urls_into_db


def test_db_deduplicates_merges_and_boosts_confidence(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    with HarvestDB(db_file) as db:
        added1, merged1 = db.upsert_batch(
            [
                CandidateRecord(
                    url="https://hertsglazing.co.uk",
                    domain="hertsglazing.co.uk",
                    source="crtsh",
                    confidence=0.80,
                    categories=["double_triple_glazing"],
                    country="GB",
                ),
                # Intra-batch duplicate from second source
                CandidateRecord(
                    url="https://hertsglazing.co.uk",
                    domain="hertsglazing.co.uk",
                    source="osm",
                    confidence=0.85,
                    categories=["upvc_vinyl"],
                    business_name="Herts Glazing Ltd",
                    city="Welwyn Garden City",
                    phone="01707 123456",
                ),
                CandidateRecord(
                    url="https://austinwindows.com",
                    domain="austinwindows.com",
                    source="overture",
                    confidence=0.90,
                    categories=["aluminium", "timber_wood"],
                    business_name="Austin Architectural Windows",
                    country="US",
                    region="TX",
                    city="Austin",
                ),
            ]
        )
        assert added1 == 2
        assert merged1 == 0
        assert db.count_domains() == 2

        # Subsequent upsert merges new source & category without losing earlier metadata
        added2, merged2 = db.upsert_batch(
            [
                CandidateRecord(
                    url="https://hertsglazing.co.uk",
                    domain="hertsglazing.co.uk",
                    source="serper_maps",
                    confidence=0.82,
                    categories=["steel_crittall"],
                    postcode="AL8 6AB",
                )
            ]
        )
        assert added2 == 0 and merged2 == 1

        rows = {r["domain"]: r for r in db.iter_domains()}
        hg = rows["hertsglazing.co.uk"]
        assert hg["business_name"] == "Herts Glazing Ltd"
        assert hg["city"] == "Welwyn Garden City"
        assert hg["postcode"] == "AL8 6AB"
        assert hg["source_count"] == 3
        assert hg["sources"] == ["crtsh", "osm", "serper_maps"]
        assert hg["categories"] == ["double_triple_glazing", "steel_crittall", "upvc_vinyl"]
        assert hg["confidence"] > 0.90  # Multi-source confidence bonus applied!

        # Checkpoints persist cleanly
        assert not db.is_checkpoint_done("osm", "country:GB")
        db.save_checkpoint("osm", "country:GB", items_found=42, meta={"ok": True})
        assert db.is_checkpoint_done("osm", "country:GB")
        assert db.get_checkpoint_meta("osm", "country:GB") == {"ok": True}

        # Export all formats + chunks + country & category splits
        out_dir = tmp_path / "out"
        exp = export_websites(
            db,
            out_dir,
            fmt="all",
            chunk_size=1,
            split_by_country=True,
            split_by_category=True,
        )
        assert exp["exported_count"] == 2

        urls = (out_dir / "urls.txt").read_text().splitlines()
        assert set(urls) == {"https://hertsglazing.co.uk", "https://austinwindows.com"}

        domains = (out_dir / "domains.txt").read_text().splitlines()
        assert set(domains) == {"hertsglazing.co.uk", "austinwindows.com"}

        with (out_dir / "websites.csv").open() as fh:
            csv_rows = list(csv.DictReader(fh))
        assert len(csv_rows) == 2

        jsonl_rows = [json.loads(line) for line in (out_dir / "websites.jsonl").read_text().splitlines()]
        assert len(jsonl_rows) == 2

        assert (out_dir / "chunks" / "urls_part_001.txt").is_file()
        assert (out_dir / "chunks" / "urls_part_002.txt").is_file()
        assert (out_dir / "by_country" / "GB_urls.txt").read_text().strip() == "https://hertsglazing.co.uk"
        assert (out_dir / "by_country" / "US_urls.txt").read_text().strip() == "https://austinwindows.com"
        assert "https://hertsglazing.co.uk" in (out_dir / "by_category" / "upvc_vinyl_urls.txt").read_text()
        assert "https://austinwindows.com" in (out_dir / "by_category" / "aluminium_urls.txt").read_text()

        # Stats check
        stats = db.get_stats()
        assert stats["total_active_domains"] == 2
        assert stats["multi_source_confirmed"] == 1
        assert stats["by_country"]["GB"] == 1
        assert stats["by_country"]["US"] == 1

        # Marking a domain parked excludes it from active exports
        db.apply_verification_batch(
            [{"domain": "austinwindows.com", "verified": int(VerifyStatus.PARKED), "http_status": 200}]
        )
        assert db.count_domains(active_only=True) == 1


def test_import_urls_from_txt_and_csv(tmp_path: Path) -> None:
    txt = tmp_path / "list.txt"
    txt.write_text(
        "\n".join(
            [
                "https://www.safestyle-windows.co.uk/contact",
                "http://safestyle-windows.co.uk",  # duplicate
                "https://crittall-windows.com",
                "https://windows11tips.com",  # MS Windows noise
                "https://www.facebook.com/safestyle",  # blocked social
            ]
        )
    )
    csv_path = tmp_path / "extra.csv"
    csv_path.write_text(
        "website,business_name,category,country,city\n"
        "https://smithjoinery.co.uk,Smith Bespoke Sash Windows,timber windows,GB,Bath\n"
        "https://yelp.com/biz/smith,Smith on Yelp,windows,US,NYC\n"
    )

    with HarvestDB(tmp_path / "imp.db") as db:
        r1 = import_urls_into_db(db, txt)
        assert r1["new_domains_added"] == 2
        assert r1["rejected"] == 2

        r2 = import_urls_into_db(db, csv_path)
        assert r2["new_domains_added"] == 1
        assert r2["rejected"] == 1
        assert db.count_domains() == 3
