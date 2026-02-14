"""Unit tests for counter_risk CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from counter_risk import cli
from tests.utils.assertions import assert_numeric_outputs_close


def _write_fixture_replay_config(config_path: Path, fixture_name: str) -> None:
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
    _write_fixture_replay_config(config_path, fixture_name)

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


@pytest.mark.parametrize(
    ("fixture_name", "payload", "abs_tol", "rel_tol"),
    [
        (
            "fixture.csv",
            [
                {"counterparty": "Alpha", "notional": 12.3456789, "notional_change": -0.125},
                {"counterparty": "Beta", "notional": -9876.54321, "notional_change": 2.5},
            ],
            1e-12,
            1e-12,
        ),
        (
            "fixture.tsv",
            [
                {"counterparty": "Gamma", "notional": 1000.0000001, "notional_change": 0.0},
                {"counterparty": "Delta", "notional": -2.125, "notional_change": -0.3333333},
            ],
            1e-9,
            1e-9,
        ),
    ],
)
def test_main_run_fixture_replay_preserves_delimited_numeric_values_with_tolerance(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    fixture_name: str,
    payload: list[dict[str, float | str]],
    abs_tol: float,
    rel_tol: float,
) -> None:
    import csv

    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    fixture_path = fixtures_dir / fixture_name
    delimiter = "\t" if fixture_name.endswith(".tsv") else ","
    with fixture_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["counterparty", "notional", "notional_change"],
            delimiter=delimiter,
        )
        writer.writeheader()
        writer.writerows(payload)

    config_path = tmp_path / "fixture_replay.yml"
    _write_fixture_replay_config(config_path, fixture_name)

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
    copied_path = output_dir / fixture_name
    with copied_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        actual_rows = [
            {
                "counterparty": row["counterparty"],
                "notional": float(row["notional"]),
                "notional_change": float(row["notional_change"]),
            }
            for row in reader
        ]

    assert_numeric_outputs_close(actual_rows, payload, abs_tol=abs_tol, rel_tol=rel_tol)


def test_main_run_fixture_replay_preserves_parquet_numeric_values_with_tolerance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pandas = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")

    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    fixture_name = "fixture.parquet"
    payload_rows = [
        {"counterparty": "Alpha", "notional": 456.0000001, "notional_change": -12.75},
        {"counterparty": "Beta", "notional": -1.25, "notional_change": 0.0000002},
    ]
    pandas.DataFrame(payload_rows).to_parquet(fixtures_dir / fixture_name, index=False)

    config_path = tmp_path / "fixture_replay.yml"
    _write_fixture_replay_config(config_path, fixture_name)

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
    copied_rows = pandas.read_parquet(output_dir / fixture_name).to_dict(orient="records")
    assert_numeric_outputs_close(copied_rows, payload_rows, abs_tol=1e-9, rel_tol=1e-9)
