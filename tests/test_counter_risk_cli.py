"""Unit tests for counter_risk CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from counter_risk import cli
from tests.utils.assertions import assert_numeric_outputs_close


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


def test_main_run_fixture_replay_preserves_json_numeric_values_with_tolerance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    fixture_name = "fixture.json"
    payload = {
        "rows": [
            {"counterparty": "Alpha", "notional": 123456.789123, "notional_change": -0.000001},
            {"counterparty": "Beta", "notional": -9876.543219, "notional_change": 0.3333333},
        ],
        "summary": {"total": 113580.245904, "change": 0.3333323},
    }
    (fixtures_dir / fixture_name).write_text(json.dumps(payload) + "\n", encoding="utf-8")

    config_path = tmp_path / "fixture_replay.yml"
    config_path.write_text(
        "\n".join(
            [
                "as_of_date: 2025-12-31",
                f"mosers_all_programs_xlsx: fixtures/{fixture_name}",
                f"mosers_ex_trend_xlsx: fixtures/{fixture_name}",
                f"mosers_trend_xlsx: fixtures/{fixture_name}",
                f"hist_all_programs_3yr_xlsx: fixtures/{fixture_name}",
                f"hist_ex_llc_3yr_xlsx: fixtures/{fixture_name}",
                f"hist_llc_3yr_xlsx: fixtures/{fixture_name}",
                f"monthly_pptx: fixtures/{fixture_name}",
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
    actual_payload = json.loads((output_dir / fixture_name).read_text(encoding="utf-8"))
    assert_numeric_outputs_close(actual_payload, payload, abs_tol=1e-10, rel_tol=1e-10)
