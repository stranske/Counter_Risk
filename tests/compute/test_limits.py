"""Tests for limit breach computations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from counter_risk.compute.limits import (
    check_limits,
    find_missing_limit_entities,
    write_limit_breaches_csv,
)
from counter_risk.limits_config import LimitsConfig


def _as_records(table: Any) -> list[dict[str, Any]]:
    if hasattr(table, "to_dict"):
        return cast(list[dict[str, Any]], table.to_dict(orient="records"))
    return [dict(row) for row in table]


def test_check_limits_detects_absolute_and_percent_breaches_across_entity_types() -> None:
    exposures = [
        {
            "counterparty": "Alpha Bank",
            "fcm": "FCM One",
            "clearing_house": "CME",
            "segment": "Treasury",
            "custom_group": "Trend Energy",
            "notional": 90.0,
        },
        {
            "counterparty": "Alpha Bank",
            "fcm": "FCM Two",
            "clearing_house": "ICE",
            "segment": "Equity",
            "custom_group": "Trend Energy",
            "notional": 30.0,
        },
        {
            "counterparty": "Beta Fund",
            "fcm": "FCM One",
            "clearing_house": "CME",
            "segment": "Commodity",
            "custom_group": "Trend Rates",
            "notional": 80.0,
        },
    ]
    limits_cfg = {
        "schema_version": 1,
        "limits": [
            {
                "entity_type": "counterparty",
                "entity_name": "Alpha Bank",
                "limit_value": 100.0,
                "limit_kind": "absolute_notional",
            },
            {
                "entity_type": "fcm",
                "entity_name": "FCM One",
                "limit_value": 0.65,
                "limit_kind": "percent_of_total",
            },
            {
                "entity_type": "clearing_house",
                "entity_name": "CME",
                "limit_value": 0.6,
                "limit_kind": "percent_of_total",
            },
            {
                "entity_type": "segment",
                "entity_name": "Treasury",
                "limit_value": 0.2,
                "limit_kind": "percent_of_total",
            },
            {
                "entity_type": "custom_group",
                "entity_name": "Trend Energy",
                "limit_value": 0.4,
                "limit_kind": "percent_of_total",
            },
        ],
    }

    rows = _as_records(check_limits(exposures, limits_cfg))

    assert rows == [
        {
            "entity_type": "clearing_house",
            "entity_name": "cme",
            "limit_kind": "percent_of_total",
            "actual_value": pytest.approx(170.0 / 200.0),
            "limit_value": 0.6,
            "breach_amount": pytest.approx((170.0 / 200.0) - 0.6),
        },
        {
            "entity_type": "counterparty",
            "entity_name": "alpha_bank",
            "limit_kind": "absolute_notional",
            "actual_value": 120.0,
            "limit_value": 100.0,
            "breach_amount": 20.0,
        },
        {
            "entity_type": "custom_group",
            "entity_name": "trend_energy",
            "limit_kind": "percent_of_total",
            "actual_value": pytest.approx(120.0 / 200.0),
            "limit_value": 0.4,
            "breach_amount": pytest.approx((120.0 / 200.0) - 0.4),
        },
        {
            "entity_type": "fcm",
            "entity_name": "fcm_one",
            "limit_kind": "percent_of_total",
            "actual_value": pytest.approx(170.0 / 200.0),
            "limit_value": 0.65,
            "breach_amount": pytest.approx((170.0 / 200.0) - 0.65),
        },
        {
            "entity_type": "segment",
            "entity_name": "treasury",
            "limit_kind": "percent_of_total",
            "actual_value": pytest.approx(90.0 / 200.0),
            "limit_value": 0.2,
            "breach_amount": pytest.approx((90.0 / 200.0) - 0.2),
        },
    ]


def test_check_limits_is_deterministic_for_reversed_rows() -> None:
    exposures = [
        {"counterparty": "A", "notional": 10.0},
        {"counterparty": "B", "notional": 9.0},
        {"counterparty": "A", "notional": 8.0},
    ]
    limits_cfg = {
        "schema_version": 1,
        "limits": [
            {
                "entity_type": "counterparty",
                "entity_name": "A",
                "limit_value": 15.0,
                "limit_kind": "absolute_notional",
            }
        ],
    }

    first = _as_records(check_limits(exposures, limits_cfg))
    second = _as_records(check_limits(list(reversed(exposures)), limits_cfg))

    assert first == second


def test_check_limits_accepts_limits_config_object() -> None:
    exposures = [{"counterparty": "A", "notional": 11.0}]
    config = LimitsConfig.model_validate(
        {
            "schema_version": 1,
            "limits": [
                {
                    "entity_type": "counterparty",
                    "entity_name": "A",
                    "limit_value": 10.0,
                    "limit_kind": "absolute_notional",
                }
            ],
        }
    )

    rows = _as_records(check_limits(exposures, config))

    assert len(rows) == 1
    assert rows[0]["breach_amount"] == 1.0


def test_check_limits_validates_exposures_input() -> None:
    with pytest.raises(TypeError, match="exposures_df must be"):
        check_limits("not-a-table", {"schema_version": 1, "limits": []})

    with pytest.raises(ValueError, match="notional values must be numeric"):
        check_limits(
            [{"counterparty": "A", "notional": "oops"}],
            {
                "schema_version": 1,
                "limits": [
                    {
                        "entity_type": "counterparty",
                        "entity_name": "A",
                        "limit_value": 1.0,
                        "limit_kind": "absolute_notional",
                    }
                ],
            },
        )


def test_check_limits_validates_limits_cfg_input() -> None:
    with pytest.raises(TypeError, match="limits_cfg must be"):
        check_limits([{"counterparty": "A", "notional": 1.0}], 123)

    with pytest.raises(ValueError, match="limits_cfg is invalid"):
        check_limits(
            [{"counterparty": "A", "notional": 1.0}],
            {
                "schema_version": 1,
                "limits": [
                    {
                        "entity_type": "counterparty",
                        "entity_name": "A",
                        "limit_kind": "absolute_notional",
                    }
                ],
            },
        )


def test_write_limit_breaches_csv_writes_expected_rows(tmp_path: Path) -> None:
    exposures = [
        {"counterparty": "A", "notional": 11.0},
        {"counterparty": "B", "notional": 1.0},
    ]
    limits_cfg = {
        "schema_version": 1,
        "limits": [
            {
                "entity_type": "counterparty",
                "entity_name": "A",
                "limit_value": 10.0,
                "limit_kind": "absolute_notional",
            }
        ],
    }
    breaches = check_limits(exposures, limits_cfg)
    out = tmp_path / "limit_breaches.csv"

    write_limit_breaches_csv(breaches, out)

    assert out.exists()
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "entity_type,entity_name,limit_kind,actual_value,limit_value,breach_amount"
    assert "counterparty,a,absolute_notional,11.0,10.0,1.0" in lines[1:]


def test_find_missing_limit_entities_returns_sorted_missing_targets() -> None:
    exposures = [
        {"counterparty": "A", "fcm": "FCM1", "notional": 11.0},
        {"counterparty": "B", "fcm": "FCM2", "notional": 1.0},
    ]
    limits_cfg = {
        "schema_version": 1,
        "limits": [
            {
                "entity_type": "counterparty",
                "entity_name": "A",
                "limit_value": 10.0,
                "limit_kind": "absolute_notional",
            },
            {
                "entity_type": "counterparty",
                "entity_name": "Missing Name",
                "limit_value": 10.0,
                "limit_kind": "absolute_notional",
            },
            {
                "entity_type": "fcm",
                "entity_name": "FCM Missing",
                "limit_value": 0.5,
                "limit_kind": "percent_of_total",
            },
        ],
    }

    missing = find_missing_limit_entities(exposures, limits_cfg)

    assert missing == [
        {"entity_type": "counterparty", "entity_name": "missing_name"},
        {"entity_type": "fcm", "entity_name": "fcm_missing"},
    ]
