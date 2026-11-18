"""Command-line interface for Window Website Harvester (`window-harvester` / `python harvest.py`)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from window_harvester import __version__
from window_harvester.classifier import classify_candidate, classify_domain_only
from window_harvester.config import PRESETS, HarvestConfig
from window_harvester.db import HarvestDB
from window_harvester.exporter import export_websites
from window_harvester.geo import generate_country_grid, get_locations
from window_harvester.models import FilterOptions
from window_harvester.pipeline import import_urls_into_db, print_db_stats, run_harvest_pipeline
from window_harvester.sources import SOURCE_REGISTRY, resolve_source_name
from window_harvester.taxonomy import CRTSH_PATTERNS, build_cdx_patterns, get_keywords_for_country
from window_harvester.verifier import verify_database_async

console = Console()


def _split_csv(raw: str | None, *, upper: bool = False) -> list[str] | None:
    if not raw:
        return None
    items = [x.strip().upper() if upper else x.strip() for x in raw.split(",") if x.strip()]
    return items or None


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="window-harvester")
def main() -> None:
    """Window Website Harvester — Collect 100,000–500,000+ window, glazing & glass business URLs."""


@main.command("run")
@click.option(
    "--preset",
    type=click.Choice(list(PRESETS.keys()), case_sensitive=False),
    default=None,
    help="Ready-made harvest strategy (e.g. free-fast, free-max, uk-complete, us-complete, global-500k).",
)
@click.option(
    "--sources",
    default=None,
    help="Comma-separated source list (e.g. overture,osm,crtsh,commoncrawl_domains,serper,google_places,ddg,yellowpages).",
)
@click.option(
    "--countries",
    default=None,
    help="Comma-separated ISO-2 country codes (e.g. GB,US,CA,AU,IE,NZ,DE,FR,NL). Omit for global.",
)
@click.option("--keyword-tier", type=click.IntRange(1, 3), default=None, help="1=core, 2=expanded, 3=exhaustive long-tail.")
@click.option("--geo-tier", type=click.IntRange(1, 3), default=None, help="1=metros, 2=all towns/cities, 3=postcodes.")
@click.option("--uk-postcodes", is_flag=True, help="Include all 121 UK Royal Mail postcode areas in search matrix.")
@click.option("--uk-postcode-districts", is_flag=True, help="Expand UK postcodes to ~2,000+ districts (AL1..ZE3).")
@click.option("--keywords", default=None, help="Override with custom comma-separated search keywords.")
@click.option("--locations-file", type=click.Path(exists=True), default=None, help="Custom .txt/.csv of cities, ZIPs or postcodes.")
@click.option("--seed-file", multiple=True, type=click.Path(exists=True), help="Custom directory URL list for trade_directories.")
@click.option("--target", type=int, default=None, help="Stop automatically once DB reaches this many unique domains.")
@click.option("--max-tasks", type=int, default=None, help="Max search tasks/queries per source (great for tests or API budgets).")
@click.option("--max-pages", type=int, default=3, show_default=True, help="Pagination depth per search/maps query.")
@click.option("--delay", type=float, default=1.0, show_default=True, help="Base delay in seconds for free scrapers.")
@click.option("--min-confidence", type=float, default=0.55, show_default=True, help="Minimum relevance score (0.0–1.0).")
@click.option("--include-treatments", is_flag=True, help="Also include pure blinds & shutters businesses.")
@click.option("--include-window-cleaning", is_flag=True, help="Also include window cleaning companies.")
@click.option("--include-auto-glass", is_flag=True, help="Also include car windscreen / auto-glass businesses.")
@click.option("--overture-release", default=None, help="Pin a specific Overture release (default: auto-detect latest).")
@click.option("--cc-webgraph-url", default=None, help="Override Common Crawl domain-ranks.txt.gz URL or local file.")
@click.option("--cc-max-scan", type=int, default=None, help="Limit number of Common Crawl domains scanned.")
@click.option("--cdx-max-pages", type=int, default=5, show_default=True, help="Max CDX pages per URL pattern.")
@click.option("--proxy", multiple=True, help="HTTP/SOCKS5 proxy URL (repeatable for rotation).")
@click.option("--show-browser", is_flag=True, help="Show visible Chromium window for playwright_gmaps.")
@click.option("--verify/--no-verify", default=False, show_default=True, help="Verify HTTP liveness & HTML after harvest.")
@click.option("--verify-concurrency", type=int, default=120, show_default=True, help="Concurrent HTTP checks when --verify is enabled.")
@click.option("--export/--no-export", default=True, show_default=True, help="Export urls.txt, domains.txt, websites.csv & jsonl after run.")
@click.option("--chunk-size", type=int, default=50_000, show_default=True, help="Also write fixed-size URL chunks (0 to disable).")
@click.option("--split-by-country", is_flag=True, help="Also export separate per-country URL files.")
@click.option("--split-by-category", is_flag=True, help="Also export separate per-category URL files (uPVC, timber, aluminium, etc.).")
@click.option("--db", "db_path", type=click.Path(), default=None, help="SQLite database path (default: data/window_websites.db).")
@click.option("--output", "output_dir", type=click.Path(), default=None, help="Export directory (default: output/).")
def cmd_run(
    preset: str | None,
    sources: str | None,
    countries: str | None,
    keyword_tier: int | None,
    geo_tier: int | None,
    uk_postcodes: bool,
    uk_postcode_districts: bool,
    keywords: str | None,
    locations_file: str | None,
    seed_file: tuple[str, ...],
    target: int | None,
    max_tasks: int | None,
    max_pages: int,
    delay: float,
    min_confidence: float,
    include_treatments: bool,
    include_window_cleaning: bool,
    include_auto_glass: bool,
    overture_release: str | None,
    cc_webgraph_url: str | None,
    cc_max_scan: int | None,
    cdx_max_pages: int,
    proxy: tuple[str, ...],
    show_browser: bool,
    verify: bool,
    verify_concurrency: int,
    export: bool,
    chunk_size: int,
    split_by_country: bool,
    split_by_category: bool,
    db_path: str | None,
    output_dir: str | None,
) -> None:
    """Run window website discovery across one or more sources (resumable anytime)."""
    cfg = HarvestConfig.from_env()
    if db_path:
        cfg.db_path = Path(db_path)
    if output_dir:
        cfg.output_dir = Path(output_dir)
    if proxy:
        cfg.proxies.extend(proxy)

    # Apply preset defaults first, then let explicit CLI flags override
    chosen_preset = (preset or ("free-fast" if not sources else "")).lower()
    if chosen_preset:
        spec = PRESETS[chosen_preset]
        cfg.countries = list(spec.countries) if spec.countries else None
        cfg.search_countries = list(spec.search_countries)
        cfg.keyword_tier = spec.keyword_tier
        cfg.geo_tier = spec.geo_tier
        cfg.include_uk_postcodes = spec.include_uk_postcodes

    explicit_ccs = _split_csv(countries, upper=True)
    if explicit_ccs:
        cfg.countries = explicit_ccs
        cfg.search_countries = explicit_ccs

    if keyword_tier is not None:
        cfg.keyword_tier = keyword_tier
    if geo_tier is not None:
        cfg.geo_tier = geo_tier
    if uk_postcodes:
        cfg.include_uk_postcodes = True
    if uk_postcode_districts:
        cfg.include_uk_postcode_districts = True
    if keywords:
        cfg.custom_keywords = _split_csv(keywords)
    if locations_file:
        cfg.custom_locations_file = locations_file
    if seed_file:
        cfg.seed_files = list(seed_file)

    cfg.target_domains = target
    cfg.max_tasks_per_source = max_tasks
    cfg.max_pages_per_query = max_pages
    cfg.request_delay = delay
    cfg.headless = not show_browser
    cfg.overture_release = overture_release
    cfg.commoncrawl_webgraph_url = cc_webgraph_url
    cfg.commoncrawl_max_domains_scan = cc_max_scan
    cfg.commoncrawl_cdx_max_pages = cdx_max_pages

    cfg.filters = FilterOptions(
        min_confidence=min_confidence,
        include_treatments=include_treatments,
        include_window_cleaning=include_window_cleaning,
        include_auto_glass=include_auto_glass,
        allowed_countries=set(cfg.countries) if cfg.countries else None,
    )

    if sources:
        try:
            source_list = [resolve_source_name(s) for s in (_split_csv(sources) or [])]
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
    else:
        source_list = cfg.resolve_preset_sources(chosen_preset)

    run_harvest_pipeline(
        cfg,
        source_list,
        verify_after=verify,
        verify_concurrency=verify_concurrency,
        export_after=export,
        chunk_size=(chunk_size if chunk_size > 0 else None),
        split_by_country=split_by_country,
        split_by_category=split_by_category,
        console=console,
    )


@main.command("sources")
def cmd_sources() -> None:
    """List all 16 website discovery sources, estimated yield, and credential readiness."""
    cfg = HarvestConfig.from_env()
    tbl = Table(title="Available Window Website Discovery Sources", show_lines=True)
    tbl.add_column("Source ID", style="bold cyan", no_wrap=True)
    tbl.add_column("Cost", no_wrap=True)
    tbl.add_column("Estimated Yield", style="green")
    tbl.add_column("Status", no_wrap=True)
    tbl.add_column("How It Works")

    # Use an in-memory DB handle only to inspect source readiness cleanly
    with HarvestDB(":memory:") as tmp_db:
        for slug, cls in SOURCE_REGISTRY.items():
            inst = cls(tmp_db, cfg)
            ok, reason = inst.is_available()
            cost = "[green]FREE ($0)[/]" if inst.is_free else "[yellow]Paid API[/]"
            if inst.is_free and inst.requires_api_key:
                cost = "[green]FREE Key[/]"
            status = "[bold green]READY[/]" if ok else f"[dim]{reason.split('(')[0].strip()}[/]"
            tbl.add_row(slug, cost, inst.estimated_yield, status, inst.description)
    console.print(tbl)


@main.command("presets")
def cmd_presets() -> None:
    """List one-command harvest presets and their expected website counts."""
    tbl = Table(title="One-Command Harvest Presets (`window-harvester run --preset <NAME>`)", show_lines=True)
    tbl.add_column("Preset", style="bold cyan", no_wrap=True)
    tbl.add_column("Expected Yield", style="bold green")
    tbl.add_column("API Keys", style="yellow")
    tbl.add_column("Description")
    for name, spec in PRESETS.items():
        tbl.add_row(name, spec.estimated_yield, spec.requires_api_keys, spec.description)
    console.print(tbl)


@main.command("plan")
@click.option("--countries", default="GB,US,CA,AU,IE,NZ", show_default=True, help="Comma-separated ISO-2 countries.")
@click.option("--keyword-tier", type=click.IntRange(1, 3), default=2, show_default=True)
@click.option("--geo-tier", type=click.IntRange(1, 3), default=2, show_default=True)
@click.option("--uk-postcodes", is_flag=True)
@click.option("--uk-postcode-districts", is_flag=True)
def cmd_plan(
    countries: str,
    keyword_tier: int,
    geo_tier: int,
    uk_postcodes: bool,
    uk_postcode_districts: bool,
) -> None:
    """Preview total search matrix size, geo-tiles, CDX patterns & CT queries before running."""
    ccs = _split_csv(countries, upper=True) or ["GB", "US"]
    tbl = Table(title="Search Matrix & Coverage Plan")
    tbl.add_column("Country", style="cyan")
    tbl.add_column("Locations", justify="right")
    tbl.add_column("Keywords", justify="right")
    tbl.add_column("Search / Maps Queries", justify="right", style="bold green")
    tbl.add_column("Root Quadtree Tiles", justify="right")

    grand_queries = 0
    grand_locs = 0
    for cc in ccs:
        locs = get_locations(
            [cc],
            max_tier=geo_tier,
            include_uk_postcodes=uk_postcodes,
            include_uk_postcode_districts=uk_postcode_districts,
        )
        kws = get_keywords_for_country(cc, max_tier=keyword_tier)
        q_count = len(locs) * len(kws)
        qt_tiles = len(generate_country_grid(cc))
        grand_locs += len(locs)
        grand_queries += q_count
        tbl.add_row(cc, f"{len(locs):,}", f"{len(kws):,}", f"{q_count:,}", f"{qt_tiles:,}" if qt_tiles else "-")

    tbl.add_section()
    tbl.add_row("TOTAL", f"{grand_locs:,}", "-", f"{grand_queries:,}", "-")
    console.print(tbl)

    cdx = build_cdx_patterns(ccs)
    console.print(
        f"\n[bold]Bulk zero-query datasets (included free):[/]\n"
        f"  • Overture Maps S3 Parquet:  [green]60,000,000+ global POIs[/] scanned in 1 SQL pass\n"
        f"  • Common Crawl WebGraph:     [green]100,000,000+ active domains[/] streamed in 1 pass\n"
        f"  • Common Crawl CDX patterns: [green]{len(cdx):,}[/] service-page wildcard patterns\n"
        f"  • Certificate Transparency:  [green]{len(CRTSH_PATTERNS):,}[/] HTTPS certificate stem queries\n"
        f"  • OpenStreetMap Overpass:    [green]{len(ccs):,}[/] country sweeps (up to 50 globally)\n"
    )


@main.command("verify")
@click.option("--db", "db_path", type=click.Path(exists=True), default="data/window_websites.db", show_default=True)
@click.option("--concurrency", type=int, default=150, show_default=True, help="Simultaneous async HTTP connections.")
@click.option("--limit", type=int, default=100_000, show_default=True, help="Max unverified domains to verify this run.")
@click.option("--timeout", "timeout_s", type=float, default=12.0, show_default=True, help="Per-site HTTP timeout (seconds).")
@click.option("--country", default=None, help="Only verify domains for a single ISO-2 country (e.g. GB).")
@click.option("--strict/--lenient", default=True, show_default=True, help="Require window keywords on live homepage HTML.")
@click.option("--reverify-errors", is_flag=True, help="Retry previously unreachable domains.")
@click.option("--include-treatments", is_flag=True)
@click.option("--include-window-cleaning", is_flag=True)
@click.option("--include-auto-glass", is_flag=True)
def cmd_verify(
    db_path: str,
    concurrency: int,
    limit: int,
    timeout_s: float,
    country: str | None,
    strict: bool,
    reverify_errors: bool,
    include_treatments: bool,
    include_window_cleaning: bool,
    include_auto_glass: bool,
) -> None:
    """Concurrently verify domains are live, non-parked, real window/glazing websites."""
    opts = FilterOptions(
        include_treatments=include_treatments,
        include_window_cleaning=include_window_cleaning,
        include_auto_glass=include_auto_glass,
    )
    with HarvestDB(db_path) as db:
        console.print(
            f"[bold cyan]Starting async live verification[/] "
            f"(concurrency={concurrency}, limit={limit:,}, timeout={timeout_s}s)..."
        )
        summary = asyncio.run(
            verify_database_async(
                db,
                options=opts,
                concurrency=concurrency,
                limit=limit,
                timeout_s=timeout_s,
                country=country,
                strict_content=strict,
                reverify_errors=reverify_errors,
                on_progress=lambda s: console.print(
                    f"  Checked [bold]{s.checked:,}[/] -> "
                    f"[green]{s.live_relevant:,} live[/] | "
                    f"{s.dead_or_error:,} dead | {s.parked:,} parked | {s.irrelevant:,} rejected"
                ),
            )
        )
        console.print(
            f"\n[bold green]Done![/] Verified {summary.checked:,} domains: "
            f"{summary.live_relevant:,} live window websites, "
            f"{summary.parked:,} parked removed, {summary.irrelevant:,} non-window removed, "
            f"{summary.dead_or_error:,} offline."
        )


@main.command("export")
@click.option("--db", "db_path", type=click.Path(exists=True), default="data/window_websites.db", show_default=True)
@click.option("--output", "output_dir", type=click.Path(), default="output", show_default=True)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["all", "txt", "domains", "csv", "jsonl"], case_sensitive=False),
    default="all",
    show_default=True,
)
@click.option("--min-confidence", type=float, default=0.55, show_default=True)
@click.option("--countries", default=None, help="Filter by comma-separated ISO-2 countries (e.g. GB,IE).")
@click.option("--categories", default=None, help="Filter by sub-categories (e.g. timber_wood,aluminium,upvc_vinyl).")
@click.option("--sources", default=None, help="Filter by discovery source (e.g. overture,serper_maps,osm).")
@click.option("--verified-only", is_flag=True, help="Export only HTTP-verified live websites.")
@click.option("--limit", type=int, default=None, help="Cap number of exported rows.")
@click.option("--chunk-size", type=int, default=50_000, show_default=True, help="Split URLs into batch files (0 to disable).")
@click.option("--split-by-country", is_flag=True, help="Write per-country URL lists in output/by_country/.")
@click.option("--split-by-category", is_flag=True, help="Write per-vertical URL lists in output/by_category/.")
def cmd_export(
    db_path: str,
    output_dir: str,
    fmt: str,
    min_confidence: float,
    countries: str | None,
    categories: str | None,
    sources: str | None,
    verified_only: bool,
    limit: int | None,
    chunk_size: int,
    split_by_country: bool,
    split_by_category: bool,
) -> None:
    """Export deduplicated website URLs to urls.txt, domains.txt, websites.csv & websites.jsonl."""
    with HarvestDB(db_path) as db:
        res = export_websites(
            db,
            output_dir,
            fmt=fmt,
            min_confidence=min_confidence,
            countries=_split_csv(countries, upper=True),
            categories=_split_csv(categories),
            sources=_split_csv(sources),
            verified_only=verified_only,
            limit=limit,
            chunk_size=(chunk_size if chunk_size > 0 else None),
            split_by_country=split_by_country,
            split_by_category=split_by_category,
        )
    console.print(f"[bold green]Exported {res['exported_count']:,} unique websites[/] to [cyan]{res['output_dir']}[/]:")
    for f in res["files"][:20]:
        console.print(f"  • {f}")
    if len(res["files"]) > 20:
        console.print(f"  • ... and {len(res['files']) - 20} more files")


@main.command("stats")
@click.option("--db", "db_path", type=click.Path(exists=True), default="data/window_websites.db", show_default=True)
def cmd_stats(db_path: str) -> None:
    """Show counts by window sub-vertical, country, source, and verification status."""
    with HarvestDB(db_path) as db:
        print_db_stats(db, console)
        stats = db.get_stats()
        if stats["by_source"]:
            stbl = Table(title="Websites by Discovery Source")
            stbl.add_column("Source", style="cyan")
            stbl.add_column("Websites", justify="right", style="bold green")
            for src, cnt in stats["by_source"].items():
                stbl.add_row(src, f"{cnt:,}")
            console.print(stbl)


@main.command("import-urls")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--db", "db_path", type=click.Path(), default="data/window_websites.db", show_default=True)
@click.option("--source-label", default="imported", show_default=True)
@click.option("--filter/--no-filter", "filter_relevance", default=True, show_default=True, help="Reject non-window & directory URLs.")
def cmd_import(file_path: str, db_path: str, source_label: str, filter_relevance: bool) -> None:
    """Merge, clean, deduplicate & classify an external .txt or .csv list of URLs."""
    with HarvestDB(db_path) as db:
        res = import_urls_into_db(
            db,
            file_path,
            source_label=source_label,
            filter_relevance=filter_relevance,
        )
        total = db.count_domains(active_only=True)
    console.print(
        f"[bold green]Import finished:[/] {res['rows_seen']:,} rows -> "
        f"+{res['new_domains_added']:,} new | {res['existing_merged']:,} merged | "
        f"{res['rejected']:,} rejected | DB total: [bold]{total:,}[/]"
    )


@main.command("classify")
@click.argument("urls", nargs=-1, required=True)
@click.option("--title", default="", help="Optional page title / business name for context.")
def cmd_classify(urls: tuple[str, ...], title: str) -> None:
    """Test the domain & context classifier on one or more sample URLs."""
    tbl = Table(title="Window Classifier Diagnostic")
    tbl.add_column("Input")
    tbl.add_column("Canonical URL", style="cyan")
    tbl.add_column("Accepted")
    tbl.add_column("Confidence", justify="right")
    tbl.add_column("Categories", style="magenta")
    tbl.add_column("Reason", style="dim")

    for u in urls:
        if title:
            norm, res = classify_candidate(u, title=title, source_trust="low")
            canon = norm.canonical_url if norm else "-"
        else:
            from window_harvester.domains import normalize_url

            norm = normalize_url(u)
            canon = norm.canonical_url if norm else "-"
            res = classify_domain_only(u)
        badge = "[bold green]YES[/]" if res.accepted else "[red]NO[/]"
        tbl.add_row(u, canon, badge, f"{res.confidence:.2f}", ", ".join(res.categories) or "-", res.reason)
    console.print(tbl)


@main.command("reset-checkpoints")
@click.option("--db", "db_path", type=click.Path(exists=True), default="data/window_websites.db", show_default=True)
@click.option("--source", default=None, help="Reset only one source (e.g. osm or serper); omit for all.")
def cmd_reset_checkpoints(db_path: str, source: str | None) -> None:
    """Clear saved progress checkpoints to force a fresh re-scan (keeps all collected URLs)."""
    src = resolve_source_name(source) if source else None
    with HarvestDB(db_path) as db:
        removed = db.clear_checkpoints(src)
    console.print(f"[green]Cleared {removed:,} checkpoint(s)[/] (all discovered websites preserved).")
