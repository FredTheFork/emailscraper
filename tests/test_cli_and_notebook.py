"""End-to-end CLI command tests and Google Colab notebook validity check."""

from __future__ import annotations

import ast
import gzip
import json
from pathlib import Path

from click.testing import CliRunner

from window_harvester.cli import main


def test_cli_full_workflow(tmp_path: Path) -> None:
    runner = CliRunner()

    # 1. `sources`, `presets`, `plan`, `classify`
    assert runner.invoke(main, ["sources"]).exit_code == 0
    assert runner.invoke(main, ["presets"]).exit_code == 0
    plan_res = runner.invoke(main, ["plan", "--countries", "GB,US", "--keyword-tier", "3", "--geo-tier", "3"])
    assert plan_res.exit_code == 0 and "TOTAL" in plan_res.output

    cls_res = runner.invoke(main, ["classify", "safestyle-windows.co.uk", "windows11tips.com"])
    assert cls_res.exit_code == 0 and "YES" in cls_res.output and "NO" in cls_res.output

    # 2. Full `run` -> `stats` -> `export` -> `reset-checkpoints` workflow on a local Common Crawl sample
    gz = tmp_path / "sample-ranks.txt.gz"
    with gzip.open(gz, "wt", encoding="utf-8") as fh:
        fh.write(
            "\n".join(
                [
                    "1\t9\t1\t9\tuk.co.watforddoubleglazing\t1",
                    "2\t8\t2\t8\tuk.co.surreytimberwindows\t1",
                    "3\t7\t3\t7\tcom.miamiimpactwindows\t1",
                    "4\t6\t4\t6\tuk.co.londonsteelwindows\t1",
                    "5\t5\t5\t5\tcom.windows11keygen\t1",
                ]
            )
            + "\n"
        )

    db_file = tmp_path / "harvest.db"
    out_dir = tmp_path / "exports"
    run_res = runner.invoke(
        main,
        [
            "run",
            "--sources",
            "commoncrawl_domains",
            "--cc-webgraph-url",
            str(gz),
            "--db",
            str(db_file),
            "--output",
            str(out_dir),
            "--split-by-country",
            "--split-by-category",
        ],
    )
    assert run_res.exit_code == 0, run_res.output
    urls = (out_dir / "urls.txt").read_text().splitlines()
    assert len(urls) == 4
    assert "https://watforddoubleglazing.co.uk" in urls
    assert not any("windows11" in u for u in urls)

    stats_res = runner.invoke(main, ["stats", "--db", str(db_file)])
    assert stats_res.exit_code == 0 and "4" in stats_res.output

    gb_dir = tmp_path / "gb_only"
    exp_res = runner.invoke(
        main,
        ["export", "--db", str(db_file), "--output", str(gb_dir), "--countries", "GB", "--format", "txt"],
    )
    assert exp_res.exit_code == 0
    gb_urls = (gb_dir / "urls.txt").read_text().splitlines()
    assert len(gb_urls) == 3

    rst_res = runner.invoke(main, ["reset-checkpoints", "--db", str(db_file), "--source", "cc"])
    assert rst_res.exit_code == 0


def test_colab_notebook_is_valid_json_and_all_code_cells_parse() -> None:
    nb_path = Path(__file__).resolve().parent.parent / "notebooks" / "Window_Website_Harvester_Colab.ipynb"
    assert nb_path.is_file()
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert len(code_cells) >= 5
    for idx, cell in enumerate(code_cells, start=1):
        src = "".join(cell["source"])
        # Wrap with `async def` to support top-level `await` in Jupyter/Colab cells
        indented = "\n".join("    " + line for line in src.splitlines())
        ast.parse(f"async def _cell_{idx}():\n{indented}\n")
