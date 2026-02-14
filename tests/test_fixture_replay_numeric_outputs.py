"""Numeric fixture replay assertions for serialized fixture formats."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from counter_risk.pipeline.fixture_replay import run_fixture_replay
from tests.utils.assertions import assert_numeric_outputs_close


def _write_fixture_config(config_path: Path, fixture_name: str) -> None:
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
                "output_root: replay-output",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _read_delimited_records(path: Path, *, delimiter: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        rows = []
        for row in reader:
            rows.append(
                {
                    "counterparty": row["counterparty"],
                    "notional": float(row["notional"]),
                    "notional_change": float(row["notional_change"]),
                }
            )
    return rows


@pytest.mark.parametrize(
    ("fixture_name", "payload", "delimiter", "abs_tol", "rel_tol"),
    [
        (
            "fixture.csv",
            [
                {
                    "counterparty": "Alpha",
                    "notional": 123456.789123,
                    "notional_change": -0.0000009,
                },
                {
                    "counterparty": "Beta",
                    "notional": -4567.000001,
                    "notional_change": 0.3333333,
                },
            ],
            ",",
            1e-12,
            1e-12,
        ),
        (
            "fixture.tsv",
            [
                {
                    "counterparty": "Gamma",
                    "notional": 10.5,
                    "notional_change": -3.1415926,
                },
                {
                    "counterparty": "Delta",
                    "notional": 9999.0002,
                    "notional_change": 2.5,
                },
            ],
            "\t",
            1e-9,
            1e-9,
        ),
    ],
)
def test_run_fixture_replay_preserves_csv_tsv_numeric_payloads(
    tmp_path: Path,
    fixture_name: str,
    payload: list[dict[str, Any]],
    delimiter: str,
    abs_tol: float,
    rel_tol: float,
) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = fixtures_dir / fixture_name
    with fixture_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["counterparty", "notional", "notional_change"],
            delimiter=delimiter,
        )
        writer.writeheader()
        writer.writerows(payload)

    config_path = tmp_path / "fixture_replay.yml"
    _write_fixture_config(config_path, fixture_name)

    run_output = run_fixture_replay(config_path=config_path)
    copied_path = run_output / fixture_name

    actual_rows = _read_delimited_records(copied_path, delimiter=delimiter)
    assert_numeric_outputs_close(actual_rows, payload, abs_tol=abs_tol, rel_tol=rel_tol)


def test_run_fixture_replay_preserves_json_numeric_payloads(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    fixture_name = "fixture.json"
    payload = {
        "rows": [
            {"counterparty": "Alpha", "notional": 1.23456789, "notional_change": -0.75},
            {"counterparty": "Beta", "notional": -5000.0, "notional_change": 2.000000001},
        ],
        "summary": {"total": -4998.76543211, "change": 1.250000001},
    }
    fixture_path = fixtures_dir / fixture_name
    fixture_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    config_path = tmp_path / "fixture_replay.yml"
    _write_fixture_config(config_path, fixture_name)

    run_output = run_fixture_replay(config_path=config_path)
    copied_path = run_output / fixture_name

    actual_payload = json.loads(copied_path.read_text(encoding="utf-8"))
    assert_numeric_outputs_close(actual_payload, payload, abs_tol=1e-10, rel_tol=1e-10)


def test_run_fixture_replay_preserves_parquet_numeric_payloads(tmp_path: Path) -> None:
    pandas = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")

    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    fixture_name = "fixture.parquet"
    payload_rows = [
        {"counterparty": "Alpha", "notional": 100.00000001, "notional_change": 0.5},
        {"counterparty": "Beta", "notional": -25.75, "notional_change": -0.125},
    ]

    fixture_path = fixtures_dir / fixture_name
    pandas.DataFrame(payload_rows).to_parquet(fixture_path, index=False)

    config_path = tmp_path / "fixture_replay.yml"
    _write_fixture_config(config_path, fixture_name)

    run_output = run_fixture_replay(config_path=config_path)
    copied_path = run_output / fixture_name

    actual_payload_rows = pandas.read_parquet(copied_path).to_dict(orient="records")
    assert_numeric_outputs_close(actual_payload_rows, payload_rows, abs_tol=1e-9, rel_tol=1e-9)
