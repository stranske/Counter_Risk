"""Limits input validation and optional table dependency contracts."""

import sys
from pathlib import Path

import pytest

from counter_risk.compute.limits import (
    _to_dataframe_or_records,
    check_limits,
    find_missing_limit_entities,
    write_limit_breaches_csv,
)
from counter_risk.limits_config import LimitEntry


def _limit(name: str = "CIBC") -> dict[str, object]:
    return {
        "entity_type": "counterparty",
        "entity_name": name,
        "limit_kind": "absolute_notional",
        "limit_value": 10.0,
    }


def test_sequence_limits_accept_models_and_mappings_and_skip_null_name_alias() -> None:
    entries = [LimitEntry.model_validate(_limit()), _limit("ASL")]
    rows = check_limits([{"counterparty": None, "name": "CIBC", "notional": -12}], entries).to_dict(
        orient="records"
    )
    assert len(rows) == 1
    assert rows[0]["entity_name"] == "cibc"
    assert rows[0]["actual_value"] == 12.0
    assert find_missing_limit_entities([], entries) == [
        {"entity_type": "counterparty", "entity_name": "asl"},
        {"entity_type": "counterparty", "entity_name": "cibc"},
    ]


@pytest.mark.parametrize(
    ("entries", "error", "message"),
    [
        ([None], TypeError, r"sequence items must be LimitEntry or mappings \(index 0\)"),
        ([{}], ValueError, "limits_cfg is invalid"),
        ([], ValueError, "limits_cfg is invalid"),
    ],
)
def test_sequence_limits_report_invalid_entries(entries, error, message) -> None:
    with pytest.raises(error, match=message):
        check_limits([], entries)


def test_exposure_row_validation_names_the_bad_index() -> None:
    with pytest.raises(TypeError, match="exposures_df row at index 1 must be a mapping"):
        check_limits([{"counterparty": "CIBC", "notional": 1}, None], [])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_limits_reject_nonfinite_exposure_magnitudes(value: float) -> None:
    with pytest.raises(ValueError, match="exposures_df notional values must be finite"):
        check_limits([{"counterparty": "CIBC", "notional": value}], [_limit()])


def test_empty_breaches_csv_truncates_stale_output(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "breaches.csv"
    path.parent.mkdir()
    path.write_text("stale breach", encoding="utf-8")
    write_limit_breaches_csv([], path)
    assert path.read_bytes() == b""


def test_missing_pandas_returns_records_with_ordered_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pandas", None)
    result = check_limits([{"counterparty": "CIBC", "notional": 12}], [_limit()])
    assert isinstance(result, list)
    assert result[0]["actual_value"] == 12.0
    assert result[0]["breach_amount"] == 2.0
    assert list(result[0]) == [
        "entity_type",
        "entity_name",
        "limit_kind",
        "severity",
        "actual_value",
        "limit_value",
        "breach_amount",
        "notes",
    ]
    assert check_limits([], [_limit()]) == []


def test_table_projection_fills_missing_columns_without_extra_fields() -> None:
    result = _to_dataframe_or_records(
        records=[{"actual_value": 12, "extra": "omit"}], columns=("notes", "actual_value")
    )
    assert list(result.columns) == ["notes", "actual_value"]
    assert result.to_dict(orient="records") == [{"notes": None, "actual_value": 12}]
