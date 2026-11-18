"""Streaming exporters for 100k–500k+ window business websites (TXT, CSV, JSONL & chunks)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from window_harvester.db import HarvestDB
from window_harvester.models import VerifyStatus

CSV_COLUMNS: tuple[str, ...] = (
    "url",
    "domain",
    "business_name",
    "categories",
    "country",
    "region",
    "city",
    "postcode",
    "phone",
    "confidence",
    "source_count",
    "sources",
    "verified_status",
    "http_status",
    "page_title",
)

_VERIFY_LABELS: dict[int, str] = {
    int(VerifyStatus.UNVERIFIED): "unverified",
    int(VerifyStatus.LIVE_RELEVANT): "verified_live",
    int(VerifyStatus.DEAD_OR_ERROR): "dead_or_error",
    int(VerifyStatus.PARKED): "parked",
    int(VerifyStatus.IRRELEVANT): "irrelevant",
}


def export_websites(
    db: HarvestDB,
    output_dir: str | Path = "output",
    *,
    fmt: str = "all",  # "all" | "txt" | "domains" | "csv" | "jsonl"
    min_confidence: float = 0.55,
    countries: list[str] | None = None,
    categories: list[str] | None = None,
    sources: list[str] | None = None,
    verified_only: bool = False,
    limit: int | None = None,
    chunk_size: int | None = None,
    split_by_country: bool = False,
    split_by_category: bool = False,
) -> dict[str, Any]:
    """Stream deduplicated window websites from SQLite to disk in constant memory.

    Returns a summary dict containing `exported_count` and `files` written.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    fmt_l = fmt.strip().lower()
    write_txt = fmt_l in ("all", "txt", "urls")
    write_domains = fmt_l in ("all", "domains")
    write_csv = fmt_l in ("all", "csv")
    write_jsonl = fmt_l in ("all", "jsonl")

    files_written: list[str] = []
    handles_to_close: list[Any] = []

    def _open_w(p: Path) -> Any:
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = p.open("w", encoding="utf-8", newline="")
        handles_to_close.append(fh)
        files_written.append(str(p))
        return fh

    txt_fh = _open_w(out / "urls.txt") if write_txt else None
    dom_fh = _open_w(out / "domains.txt") if write_domains else None
    csv_fh = _open_w(out / "websites.csv") if write_csv else None
    jsonl_fh = _open_w(out / "websites.jsonl") if write_jsonl else None

    csv_writer = csv.writer(csv_fh) if csv_fh else None
    if csv_writer:
        csv_writer.writerow(CSV_COLUMNS)

    chunk_fh: Any = None
    chunk_idx = 0
    country_fhs: dict[str, Any] = {}
    category_fhs: dict[str, Any] = {}
    count = 0

    try:
        for row in db.iter_domains(
            min_confidence=min_confidence,
            countries=countries,
            categories=categories,
            sources=sources,
            verified_only=verified_only,
            limit=limit,
        ):
            best_url = str(row.get("final_url") or row["url"]).strip()
            # Keep URL list clean as root/canonical URLs unless final_url resolved to www
            if not best_url.startswith(("http://", "https://")):
                best_url = str(row["url"])
            domain = str(row["domain"])
            cats: list[str] = row["categories"]
            srcs: list[str] = row["sources"]
            vlabel = _VERIFY_LABELS.get(int(row.get("verified") or 0), "unverified")

            if txt_fh:
                txt_fh.write(best_url + "\n")
            if dom_fh:
                dom_fh.write(domain + "\n")
            if csv_writer:
                csv_writer.writerow(
                    [
                        best_url,
                        domain,
                        row.get("business_name") or "",
                        "|".join(cats),
                        row.get("country") or "",
                        row.get("region") or "",
                        row.get("city") or "",
                        row.get("postcode") or "",
                        row.get("phone") or "",
                        row.get("confidence") or "",
                        row.get("source_count") or 1,
                        "|".join(srcs),
                        vlabel,
                        row.get("http_status") or "",
                        row.get("page_title") or "",
                    ]
                )
            if jsonl_fh:
                payload = {
                    "url": best_url,
                    "domain": domain,
                    "business_name": row.get("business_name"),
                    "categories": cats,
                    "country": row.get("country"),
                    "region": row.get("region"),
                    "city": row.get("city"),
                    "postcode": row.get("postcode"),
                    "address": row.get("address"),
                    "phone": row.get("phone"),
                    "lat": row.get("lat"),
                    "lon": row.get("lon"),
                    "confidence": row.get("confidence"),
                    "source_count": row.get("source_count"),
                    "sources": srcs,
                    "verified_status": vlabel,
                    "http_status": row.get("http_status"),
                    "page_title": row.get("page_title"),
                    "meta_description": row.get("meta_description"),
                }
                jsonl_fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

            # Optional fixed-size batch files (e.g. 50,000 URLs each for Google Sheets / scrapers)
            if chunk_size and chunk_size > 0:
                if count % chunk_size == 0:
                    chunk_idx += 1
                    chunk_fh = _open_w(out / "chunks" / f"urls_part_{chunk_idx:03d}.txt")
                chunk_fh.write(best_url + "\n")

            if split_by_country:
                cc = (row.get("country") or "UNKNOWN").upper()
                fh = country_fhs.get(cc)
                if fh is None:
                    fh = _open_w(out / "by_country" / f"{cc}_urls.txt")
                    country_fhs[cc] = fh
                fh.write(best_url + "\n")

            if split_by_category:
                for cat in cats or ["general_windows"]:
                    safe_cat = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in cat)
                    fh = category_fhs.get(safe_cat)
                    if fh is None:
                        fh = _open_w(out / "by_category" / f"{safe_cat}_urls.txt")
                        category_fhs[safe_cat] = fh
                    fh.write(best_url + "\n")

            count += 1

        if fmt_l == "all":
            summary_path = out / "summary.json"
            stats = db.get_stats()
            stats["exported_count"] = count
            summary_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
            files_written.append(str(summary_path))
    finally:
        for fh in handles_to_close:
            try:
                fh.close()
            except Exception:
                pass

    return {
        "exported_count": count,
        "output_dir": str(out),
        "files": files_written,
    }
