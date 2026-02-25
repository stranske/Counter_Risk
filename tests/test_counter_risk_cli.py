"""Unit tests for counter_risk CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from counter_risk import cli


def test_main_without_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.main([])
    captured = capsys.readouterr()

    assert result == 0
    assert "usage:" in captured.out.lower()


def test_main_run_command_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.main(["run"])
    captured = capsys.readouterr()

    assert result == 0
    assert "not implemented yet" in captured.out.lower()


def test_run_parser_accepts_export_pdf_flags() -> None:
    parser = cli.build_parser()

    args_true = parser.parse_args(["run", "--export-pdf"])
    assert args_true.export_pdf is True

    args_false = parser.parse_args(["run", "--no-export-pdf"])
    assert args_false.export_pdf is False


def test_run_parser_accepts_dry_run_discovery_and_as_of_month() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["run", "--dry-run-discovery", "--as-of-month", "2025-12-31"])
    assert args.dry_run_discovery is True
    assert args.as_of_month == "2025-12-31"


def test_main_run_dry_run_discovery_lists_matches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monthly_root = tmp_path / "monthly"
    historical_root = tmp_path / "historical"
    template_root = tmp_path / "templates"
    for root in (monthly_root, historical_root, template_root):
        root.mkdir(parents=True)

    (monthly_root / "NISA Monthly All Programs - Raw.xlsx").write_text("x", encoding="utf-8")
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "Daily Holdings 2025-12-31.pdf").write_text("x", encoding="utf-8")
    (historical_root / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (historical_root / "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (historical_root / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (template_root / "Monthly Counterparty Exposure Report.pptx").write_text("x", encoding="utf-8")

    config_path = tmp_path / "dry_run_discovery.yml"
    config_path.write_text(
        "\n".join(
            [
                "mosers_ex_trend_xlsx: tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
                "mosers_trend_xlsx: tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
                "hist_all_programs_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "hist_ex_llc_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "hist_llc_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "monthly_pptx: tests/fixtures/Monthly Counterparty Exposure Report.pptx",
                "input_discovery:",
                "  directory_roots:",
                f"    monthly_inputs: {monthly_root}",
                f"    historical_inputs: {historical_root}",
                f"    template_inputs: {template_root}",
                "  naming_patterns:",
                "    raw_nisa_all_programs_xlsx:",
                "      - NISA Monthly All Programs - Raw.xlsx",
                "    mosers_all_programs_xlsx:",
                "      - MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - All Programs.xlsx",
                "    mosers_ex_trend_xlsx:",
                "      - MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - Ex Trend.xlsx",
                "    mosers_trend_xlsx:",
                "      - MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - Trend.xlsx",
                "    daily_holdings_pdf:",
                "      - Daily Holdings {as_of_date}.pdf",
                "    hist_all_programs_3yr_xlsx:",
                "      - Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "    hist_ex_llc_3yr_xlsx:",
                "      - Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "    hist_llc_3yr_xlsx:",
                "      - Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "    monthly_pptx:",
                "      - Monthly Counterparty Exposure Report*.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "run",
            "--dry-run-discovery",
            "--config",
            str(config_path),
            "--as-of-month",
            "2025-12-31",
        ]
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "Discovery dry-run for as-of date 2025-12-31" in captured.out
    assert "- monthly_pptx: 1 match(es)" in captured.out
    assert "Monthly Counterparty Exposure Report.pptx" in captured.out
    assert "- raw_nisa_all_programs_xlsx: 1 match(es)" in captured.out
    assert "NISA Monthly All Programs - Raw.xlsx" in captured.out


def test_main_run_dry_run_discovery_requires_as_of_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "dry_run_discovery_missing_as_of.yml"
    config_path.write_text(
        "\n".join(
            [
                "mosers_ex_trend_xlsx: tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
                "mosers_trend_xlsx: tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
                "hist_all_programs_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "hist_ex_llc_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "hist_llc_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "monthly_pptx: tests/fixtures/Monthly Counterparty Exposure Report.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = cli.main(["run", "--dry-run-discovery", "--config", str(config_path)])
    captured = capsys.readouterr()

    assert result == 2
    assert "requires an as-of date" in captured.out


def test_main_run_fixture_replay_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    fixture_names = [
        "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
        "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
        "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
        "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
        "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
        "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
        "Monthly Counterparty Exposure Report.pptx",
    ]
    for name in fixture_names:
        (fixtures_dir / name).write_text(name, encoding="utf-8")

    config_path = tmp_path / "fixture_replay.yml"
    config_path.write_text(
        "\n".join(
            [
                "as_of_date: 2025-12-31",
                "mosers_all_programs_xlsx: fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
                "mosers_ex_trend_xlsx: fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
                "mosers_trend_xlsx: fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
                "hist_all_programs_3yr_xlsx: fixtures/Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "hist_ex_llc_3yr_xlsx: fixtures/Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "hist_llc_3yr_xlsx: fixtures/Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "monthly_pptx: fixtures/Monthly Counterparty Exposure Report.pptx",
                "output_root: run-output",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "run-output"
    result = cli.main(
        [
            "run",
            "--fixture-replay",
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "fixture replay completed" in captured.out.lower()
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "fixture_replay"
