"""Integration coverage for `counter-risk run` workflow-mode execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _write_workflow_config(
    *,
    path: Path,
    fixtures_root: Path,
    missing_ex_trend_input: bool = False,
) -> None:
    ex_trend_path = fixtures_root / "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx"
    if missing_ex_trend_input:
        ex_trend_path = fixtures_root / "DOES_NOT_EXIST-Ex Trend.xlsx"

    lines = [
        "as_of_date: 2025-12-31",
        f"mosers_all_programs_xlsx: {fixtures_root / 'MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx'}",
        f"mosers_ex_trend_xlsx: {ex_trend_path}",
        f"mosers_trend_xlsx: {fixtures_root / 'MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx'}",
        f"hist_all_programs_3yr_xlsx: {fixtures_root / 'Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx'}",
        f"hist_ex_llc_3yr_xlsx: {fixtures_root / 'Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx'}",
        f"hist_llc_3yr_xlsx: {fixtures_root / 'Historical Counterparty Risk Graphs - LLC 3 Year.xlsx'}",
        f"monthly_pptx: {fixtures_root / 'Monthly Counterparty Exposure Report.pptx'}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_cli(*, repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"
    )
    return subprocess.run(
        [sys.executable, "-m", "counter_risk.cli", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_cli_run_workflow_mode_writes_manifest_and_data_quality_summary(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixtures_root = repo_root / "tests" / "fixtures"
    config_path = tmp_path / "workflow.yml"
    run_dir = tmp_path / "run-output"
    _write_workflow_config(path=config_path, fixtures_root=fixtures_root)

    result = _run_cli(
        repo_root=repo_root,
        args=[
            "run",
            "--config",
            str(config_path),
            "--as-of-date",
            "2025-12-31",
            "--output-dir",
            str(run_dir),
        ],
    )

    assert result.returncode == 0, (
        "Workflow-mode run failed unexpectedly.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "Counter Risk run completed:" in result.stdout
    manifest_path = run_dir / "manifest.json"
    summary_path = run_dir / "DATA_QUALITY_SUMMARY.txt"
    assert manifest_path.is_file()
    assert summary_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "DATA_QUALITY_SUMMARY.txt" in manifest["output_paths"]
    assert manifest["as_of_date"] == "2025-12-31"


def test_cli_run_workflow_mode_reports_missing_inputs(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixtures_root = repo_root / "tests" / "fixtures"
    config_path = tmp_path / "workflow-missing-input.yml"
    run_dir = tmp_path / "run-output"
    _write_workflow_config(
        path=config_path,
        fixtures_root=fixtures_root,
        missing_ex_trend_input=True,
    )

    result = _run_cli(
        repo_root=repo_root,
        args=[
            "run",
            "--config",
            str(config_path),
            "--as-of-date",
            "2025-12-31",
            "--output-dir",
            str(run_dir),
        ],
    )

    assert result.returncode != 0
    assert "Counter Risk run failed:" in result.stdout
    assert "input validation" in result.stdout.casefold()
    assert "verify required input files" in result.stdout.casefold()
