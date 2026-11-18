"""Async tests for the live website HTTP verifier, parked-domain detector & Colab loop safety."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import aiohttp
from aiohttp import web

from window_harvester.db import HarvestDB
from window_harvester.models import CandidateRecord, FilterOptions, VerifyStatus
from window_harvester.verifier import probe_single_domain, run_verify_sync


async def test_probe_single_domain_against_real_local_http_server() -> None:
    async def handle_real(_req: web.Request) -> web.Response:
        return web.Response(
            text=(
                "<html><head><title>Welwyn Double Glazing & Timber Sash Windows</title>"
                "<meta name='description' content='uPVC and aluminium window suppliers in Hertfordshire.'></head>"
                "<body><h1>Double Glazing Installers</h1></body></html>"
            ),
            content_type="text/html",
        )

    async def handle_parked(_req: web.Request) -> web.Response:
        return web.Response(
            text="<html><head><title>This domain is for sale | SedoParking.com</title></head><body>Buy this domain</body></html>",
            content_type="text/html",
        )

    async def handle_mswin(_req: web.Request) -> web.Response:
        return web.Response(
            text="<html><head><title>Best Free Antivirus Download for Microsoft Windows 11</title></head><body>PC tool</body></html>",
            content_type="text/html",
        )

    app = web.Application()
    app.router.add_get("/real", handle_real)
    app.router.add_get("/parked", handle_parked)
    app.router.add_get("/mswin", handle_mswin)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]

    try:
        # Allow 127.0.0.1 through normalize_url strictly for local loopback test server
        from window_harvester.domains import NormalizedDomain

        fake_norm = NormalizedDomain(
            domain="welwynglazing.co.uk",
            canonical_url="https://welwynglazing.co.uk",
            sld="welwynglazing",
            suffix="co.uk",
            inferred_country="GB",
            original_path="/",
        )
        with patch("window_harvester.verifier.normalize_url", return_value=fake_norm):
            async with aiohttp.ClientSession() as session:
                r_live = await probe_single_domain(
                    session,
                    "welwynglazing.co.uk",
                    f"http://127.0.0.1:{port}/real",
                    FilterOptions(),
                )
                assert r_live["verified"] == int(VerifyStatus.LIVE_RELEVANT)
                assert r_live["http_status"] == 200
                assert "upvc_vinyl" in r_live["categories"]
                assert "aluminium" in r_live["categories"]

                r_parked = await probe_single_domain(
                    session,
                    "oldwindows.com",
                    f"http://127.0.0.1:{port}/parked",
                    FilterOptions(),
                )
                assert r_parked["verified"] == int(VerifyStatus.PARKED)

                r_ms = await probe_single_domain(
                    session,
                    "winhelper.com",
                    f"http://127.0.0.1:{port}/mswin",
                    FilterOptions(),
                )
                assert r_ms["verified"] == int(VerifyStatus.IRRELEVANT)
    finally:
        await runner.cleanup()


async def test_run_verify_sync_works_inside_running_event_loop(tmp_path: Path) -> None:
    """Ensure Colab/Jupyter's already-running asyncio loop never triggers RuntimeError."""
    with HarvestDB(tmp_path / "empty.db") as db:
        summary = run_verify_sync(db=db, limit=10)
        assert summary.checked == 0

    with HarvestDB(tmp_path / "one.db") as db:
        db.upsert_record(
            CandidateRecord(
                url="http://127.0.0.1:1",
                domain="unreachable-test-window.co.uk",
                source="test",
            )
        )
        summary2 = run_verify_sync(db=db, limit=5, timeout_s=0.3, concurrency=2)
        assert summary2.checked == 1
        assert summary2.dead_or_error == 1
