"""Multi-source harvest orchestrator, external list importer & live progress reporter."""

from __future__ import annotations

import csv
import signal
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from window_harvester.classifier import classify_candidate, classify_domain_only
from window_harvester.config import HarvestConfig
from window_harvester.db import HarvestDB
from window_harvester.domains import normalize_url
from window_harvester.exporter import export_websites
from window_harvester.models import CandidateRecord, FilterOptions, SourceRunResult, WINDOW_CATEGORIES
from window_harvester.sources import SOURCE_REGISTRY, resolve_source_name
from window_harvester.verifier import run_verify_sync


def run_harvest_pipeline(
    config: HarvestConfig,
    source_names: list[str],
    *,
    verify_after: bool = False,
    verify_concurrency: int = 120,
    verify_limit: int = 100_000,
    export_after: bool = True,
    chunk_size: int | None = 50_000,
    split_by_country: bool = False,
    split_by_category: bool = False,
    console: Console | None = None,
) -> list[SourceRunResult]:
    """Run an ordered sequence of discovery sources into a single deduplicated SQLite DB."""
    con = console or Console()
    resolved = list(dict.fromkeys(resolve_source_name(s) for s in source_names))

    interrupted = False
    prev_handler = signal.getsignal(signal.SIGINT)

    def _handle_sigint(_sig: int, _frame: Any) -> None:
        nonlocal interrupted
        interrupted = True
        con.print("\n[bold yellow]Interrupt received — flushing buffers & saving SQLite checkpoints cleanly...[/]")

    try:
        signal.signal(signal.SIGINT, _handle_sigint)
    except ValueError:
        # Running inside a non-main thread (e.g. notebook background thread)
        prev_handler = None

    results: list[SourceRunResult] = []

    try:
        with HarvestDB(config.db_path) as db:
            starting_total = db.count_domains(active_only=True)
            con.print(
                Panel.fit(
                    f"[bold cyan]Window Website Harvester[/]\n"
                    f"Database: [green]{config.db_path}[/] (starting with [bold]{starting_total:,}[/] domains)\n"
                    f"Sources:  [yellow]{', '.join(resolved)}[/]\n"
                    f"Scope:    [magenta]{', '.join(config.countries) if config.countries else 'GLOBAL (All Countries)'}[/]"
                    + (f"\nTarget:   [bold green]{config.target_domains:,}[/] domains" if config.target_domains else ""),
                    border_style="cyan",
                )
            )

            for src_name in resolved:
                if interrupted:
                    break
                if config.target_domains and db.count_domains(active_only=True) >= config.target_domains:
                    con.print(f"[bold green]Reached target of {config.target_domains:,} unique domains![/]")
                    break

                src_cls = SOURCE_REGISTRY[src_name]

                def _progress(name: str, msg: str, _res: SourceRunResult) -> None:
                    con.print(f"  [dim][{name}][/] {msg}")

                source = src_cls(
                    db,
                    config,
                    on_progress=_progress,
                    stop_check=lambda: interrupted,
                )

                ready, reason = source.is_available()
                if not ready:
                    con.print(f"[yellow]Skipping [bold]{src_name}[/]: {reason}[/]")
                    skipped = SourceRunResult(source=src_name, notes=f"Skipped: {reason}")
                    results.append(skipped)
                    continue

                con.print(f"\n[bold cyan]▶ Running {source.display_name}[/] [dim]({src_name})[/]")
                try:
                    res = source.run()
                except Exception as exc:
                    con.print(f"[red]  ✗ {src_name} stopped with error: {exc}[/]")
                    res = source.result
                    if not res.notes:
                        res.notes = str(exc)

                results.append(res)
                total_now = db.count_domains(active_only=True)
                con.print(
                    f"[green]  ✓ {src_name} finished in {res.elapsed_seconds:.1f}s:[/] "
                    f"+[bold]{res.new_domains_added:,}[/] new | "
                    f"{res.existing_domains_merged:,} cross-confirmed | "
                    f"DB total: [bold green]{total_now:,}[/] unique websites"
                )
                if res.notes:
                    con.print(f"  [dim]Note: {res.notes}[/]")

            # Optional live async HTTP verification pass
            if verify_after and not interrupted:
                con.print(
                    f"\n[bold cyan]▶ Verifying live websites[/] "
                    f"(concurrency={verify_concurrency}, limit={verify_limit:,})..."
                )
                vsum = run_verify_sync(
                    db=db,
                    options=config.filters,
                    concurrency=verify_concurrency,
                    limit=verify_limit,
                    on_progress=lambda s: con.print(
                        f"  [dim][verify][/] Checked {s.checked:,}: "
                        f"[green]{s.live_relevant:,} live[/] | "
                        f"{s.dead_or_error:,} dead | {s.parked:,} parked | {s.irrelevant:,} filtered"
                    ),
                )
                con.print(
                    f"[green]  ✓ Verification complete:[/] {vsum.live_relevant:,}/{vsum.checked:,} confirmed live window sites"
                )

            print_run_summary_table(results, con)
            print_db_stats(db, con)

            if export_after and db.count_domains(active_only=True) > 0:
                exp = export_websites(
                    db,
                    config.output_dir,
                    fmt="all",
                    min_confidence=config.filters.min_confidence,
                    countries=config.countries,
                    chunk_size=chunk_size,
                    split_by_country=split_by_country,
                    split_by_category=split_by_category,
                )
                con.print(
                    Panel.fit(
                        f"[bold green]Exported {exp['exported_count']:,} unique window business websites![/]\n"
                        f"Pure URL list:  [bold]{config.output_dir / 'urls.txt'}[/]\n"
                        f"Root domains:   [bold]{config.output_dir / 'domains.txt'}[/]\n"
                        f"Full CSV table: [bold]{config.output_dir / 'websites.csv'}[/]\n"
                        f"JSONL records:  [bold]{config.output_dir / 'websites.jsonl'}[/]",
                        border_style="green",
                    )
                )
    finally:
        if prev_handler is not None:
            signal.signal(signal.SIGINT, prev_handler)

    return results


def import_urls_into_db(
    db: HarvestDB,
    file_path: str | Path,
    *,
    source_label: str = "imported",
    filter_relevance: bool = True,
    options: FilterOptions | None = None,
) -> dict[str, int]:
    """Import, normalize, deduplicate & optionally classify URLs from any `.txt` or `.csv` file."""
    opts = options or FilterOptions()
    p = Path(file_path)
    text = p.read_text(encoding="utf-8", errors="replace")

    seen = 0
    rejected = 0
    added_total = 0
    merged_total = 0
    batch: list[CandidateRecord] = []

    def _flush_batch() -> None:
        nonlocal added_total, merged_total
        if batch:
            a, m = db.upsert_batch(batch)
            added_total += a
            merged_total += m
            batch.clear()

    if p.suffix.lower() == ".csv":
        reader = csv.DictReader(text.splitlines())
        for row in reader:
            nrow = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            raw_url = (
                nrow.get("url")
                or nrow.get("website")
                or nrow.get("domain")
                or nrow.get("site")
                or nrow.get("link")
                or ""
            )
            if not raw_url:
                continue
            seen += 1
            bname = nrow.get("business_name") or nrow.get("name") or nrow.get("company") or nrow.get("title") or ""
            cat = nrow.get("category") or nrow.get("categories") or ""
            country = nrow.get("country") or ""
            city = nrow.get("city") or ""
            region = nrow.get("region") or nrow.get("state") or ""
            phone = nrow.get("phone") or ""

            if filter_relevance:
                norm, cls = classify_candidate(
                    raw_url,
                    business_name=bname,
                    category_hint=cat,
                    source_trust="medium" if (bname or cat) else "low",
                    options=opts,
                )
                if norm is None or not cls.accepted:
                    rejected += 1
                    continue
                cats, conf = cls.categories, cls.confidence
            else:
                norm = normalize_url(raw_url)
                if norm is None:
                    rejected += 1
                    continue
                dom_cls = classify_domain_only(norm, opts)
                cats = dom_cls.categories or ["general_windows"]
                conf = max(0.75, dom_cls.confidence)

            batch.append(
                CandidateRecord(
                    url=norm.canonical_url,
                    domain=norm.domain,
                    source=source_label,
                    confidence=conf,
                    categories=cats,
                    business_name=bname or None,
                    country=(country.upper()[:2] if len(country) == 2 else norm.inferred_country),
                    region=region or None,
                    city=city or None,
                    phone=phone or None,
                    sample_query=f"import:{p.name}",
                )
            )
            if len(batch) >= 1000:
                _flush_batch()
    else:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            seen += 1
            norm = normalize_url(line)
            if norm is None:
                rejected += 1
                continue
            dom_cls = classify_domain_only(norm, opts)
            if filter_relevance and not dom_cls.accepted:
                rejected += 1
                continue
            batch.append(
                CandidateRecord(
                    url=norm.canonical_url,
                    domain=norm.domain,
                    source=source_label,
                    confidence=dom_cls.confidence if dom_cls.accepted else 0.75,
                    categories=dom_cls.categories or ["general_windows"],
                    country=norm.inferred_country,
                    sample_query=f"import:{p.name}",
                )
            )
            if len(batch) >= 1000:
                _flush_batch()

    _flush_batch()
    return {
        "rows_seen": seen,
        "new_domains_added": added_total,
        "existing_merged": merged_total,
        "rejected": rejected,
    }


def print_run_summary_table(results: list[SourceRunResult], console: Console) -> None:
    if not results:
        return
    tbl = Table(title="Harvest Run Summary by Source", show_lines=False)
    tbl.add_column("Source", style="cyan")
    tbl.add_column("Tasks", justify="right")
    tbl.add_column("Seen", justify="right")
    tbl.add_column("New Domains", justify="right", style="bold green")
    tbl.add_column("Merged", justify="right")
    tbl.add_column("Filtered", justify="right", style="dim")
    tbl.add_column("Time (s)", justify="right")

    for r in results:
        tbl.add_row(
            r.source,
            f"{r.tasks_completed:,}",
            f"{r.candidates_seen:,}",
            f"+{r.new_domains_added:,}",
            f"{r.existing_domains_merged:,}",
            f"{r.rejected_count:,}",
            f"{r.elapsed_seconds:.1f}",
        )
    console.print()
    console.print(tbl)


def print_db_stats(db: HarvestDB, console: Console) -> None:
    stats = db.get_stats()
    ver = stats["verification"]
    console.print(
        Panel.fit(
            f"[bold]Total Unique Window Websites:[/] [bold green]{stats['total_active_domains']:,}[/]\n"
            f"High-Confidence (>=0.80):     [cyan]{stats['high_confidence_domains']:,}[/]\n"
            f"Multi-Source Confirmed:       [cyan]{stats['multi_source_confirmed']:,}[/]\n"
            f"Verification:                 [green]{ver['verified_live']:,} live[/] | "
            f"{ver['unverified']:,} unverified | {ver['dead_or_error']:,} dead | "
            f"{ver['parked']:,} parked | {ver['rejected_irrelevant']:,} rejected",
            title="Master Database Overview",
            border_style="blue",
        )
    )

    if stats["by_category"]:
        ctbl = Table(title="Breakdown by Window Sub-Vertical")
        ctbl.add_column("Category", style="magenta")
        ctbl.add_column("Description")
        ctbl.add_column("Websites", justify="right", style="bold")
        for slug, cnt in list(stats["by_category"].items())[:16]:
            ctbl.add_row(slug, WINDOW_CATEGORIES.get(slug, slug), f"{cnt:,}")
        console.print(ctbl)

    if stats["by_country"]:
        gtbl = Table(title="Top Countries")
        gtbl.add_column("Country", style="yellow")
        gtbl.add_column("Websites", justify="right", style="bold")
        for cc, cnt in list(stats["by_country"].items())[:15]:
            gtbl.add_row(cc, f"{cnt:,}")
        console.print(gtbl)
