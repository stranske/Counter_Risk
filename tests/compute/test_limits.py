"""Tests for limit breach computations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from counter_risk.compute.limits import (
    _COUNTERPARTY_GRANULARITY,
    _FUTURES_GRANULARITY,
    _LIMIT_GRANULARITY_KEY,
    _find_notional,
    check_limits,
    find_missing_limit_entities,
    write_limit_breaches_csv,
)
from counter_risk.limits_config import LimitsConfig


def _as_records(table: Any) -> list[dict[str, Any]]:
    if hasattr(table, "to_dict"):
        return cast(list[dict[str, Any]], table.to_dict(orient="records"))
    return [dict(row) for row in table]


@pytest.mark.parametrize("blank", [None, "", " \t "])
@pytest.mark.parametrize("fallback", ["Notional", "exposure", "total", "amount"])
def test_find_notional_skips_blank_aliases(blank: Any, fallback: str) -> None:
    assert _find_notional({"notional": blank, fallback: 250000.0}) == 250000.0


@pytest.mark.parametrize("value", [True, False])
@pytest.mark.parametrize("key", ["notional", "Notional", "exposure", "total", "amount"])
def test_find_notional_rejects_boolean_aliases(value: bool, key: str) -> None:
    with pytest.raises(ValueError, match="notional values must be numeric"):
        _find_notional({key: value})


def test_find_notional_preserves_precedence_zero_and_invalid_value_rejection() -> None:
    assert _find_notional({"notional": 0, "exposure": 250000.0}) == 0.0
    assert _find_notional({"notional": "-125.5", "exposure": 250000.0}) == -125.5
    assert _find_notional({"amount": "250000"}) == 250000.0
    for invalid in (True, False, "oops", []):
        with pytest.raises(ValueError, match="notional values must be numeric"):
            _find_notional({"notional": invalid, "exposure": 250000.0})


@pytest.mark.parametrize("row", [{}, {"notional": None, "exposure": "", "amount": " "}])
def test_find_notional_rejects_rows_without_usable_aliases(row: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="must include one of the notional columns"):
        _find_notional(row)


def test_check_limits_uses_fallback_notional_for_breaches_and_denominator() -> None:
    exposures = [
        {"counterparty": "Alpha", "notional": None, "Notional": "", "exposure": 250000.0},
        {"counterparty": "Beta", "notional": " ", "exposure": None, "amount": 750000.0},
    ]
    config = {
        "schema_version": 1,
        "limits": [
            {
                "entity_type": "counterparty",
                "entity_name": "Alpha",
                "limit_kind": kind,
                "limit_value": limit,
            }
            for kind, limit in [("absolute_notional", 200000.0), ("percent_of_total", 0.2)]
        ],
    }
    rows = _as_records(check_limits(exposures, config))
    by_kind = {row["limit_kind"]: row for row in rows}
    assert set(by_kind) == {"absolute_notional", "percent_of_total"}
    assert by_kind["absolute_notional"]["actual_value"] == 250000.0
    assert by_kind["absolute_notional"]["breach_amount"] == 50000.0
    assert by_kind["percent_of_total"]["actual_value"] == pytest.approx(0.25)
    assert by_kind["percent_of_total"]["breach_amount"] == pytest.approx(0.05)


@pytest.mark.parametrize("enabled", [True, False])
def test_finite_limit_preserves_breach_and_disabled_behavior(enabled: bool) -> None:
    config = {
        "schema_version": 1,
        "limits": [
            {
                "entity_type": "counterparty",
                "entity_name": "Alpha",
                "limit_kind": "absolute_notional",
                "limit_value": 50,
                "severity": "fail",
                "enabled": enabled,
            }
        ],
    }
    rows = _as_records(check_limits([{"counterparty": "Alpha", "notional": 100}], config))
    if enabled:
        assert len(rows) == 1
        assert rows[0]["actual_value"] == 100
        assert rows[0]["limit_value"] == 50
        assert rows[0]["breach_amount"] == 50
        assert rows[0]["severity"] == "fail"
    else:
        assert rows == []


@pytest.mark.parametrize("limit_kind", ["absolute_notional", "percent_of_total"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_check_limits_rejects_non_finite_policy_before_evaluation(
    monkeypatch: pytest.MonkeyPatch, limit_kind: str, value: float
) -> None:
    def unexpected_evaluation(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Non-finite policy reached exposure evaluation")

    monkeypatch.setattr(
        "counter_risk.compute.limits._denominator_abs_notional", unexpected_evaluation
    )
    config = {
        "schema_version": 1,
        "limits": [
            {
                "entity_type": "counterparty",
                "entity_name": "Alpha",
                "limit_kind": limit_kind,
                "limit_value": value,
            }
        ],
    }
    with pytest.raises(ValueError, match=r"limit_value\s+Input should be a finite number"):
        check_limits([{"counterparty": "Alpha", "notional": 100}], config)


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
                "severity": "fail",
                "notes": "Single-name cap.",
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
            "severity": "warning",
            "actual_value": pytest.approx(170.0 / 200.0),
            "limit_value": 0.6,
            "breach_amount": pytest.approx((170.0 / 200.0) - 0.6),
            "notes": None,
        },
        {
            "entity_type": "counterparty",
            "entity_name": "alpha_bank",
            "limit_kind": "absolute_notional",
            "severity": "fail",
            "actual_value": 120.0,
            "limit_value": 100.0,
            "breach_amount": 20.0,
            "notes": "Single-name cap.",
        },
        {
            "entity_type": "custom_group",
            "entity_name": "trend_energy",
            "limit_kind": "percent_of_total",
            "severity": "warning",
            "actual_value": pytest.approx(120.0 / 200.0),
            "limit_value": 0.4,
            "breach_amount": pytest.approx((120.0 / 200.0) - 0.4),
            "notes": None,
        },
        {
            "entity_type": "fcm",
            "entity_name": "fcm_one",
            "limit_kind": "percent_of_total",
            "severity": "warning",
            "actual_value": pytest.approx(170.0 / 200.0),
            "limit_value": 0.65,
            "breach_amount": pytest.approx((170.0 / 200.0) - 0.65),
            "notes": None,
        },
        {
            "entity_type": "segment",
            "entity_name": "treasury",
            "limit_kind": "percent_of_total",
            "severity": "warning",
            "actual_value": pytest.approx(90.0 / 200.0),
            "limit_value": 0.2,
            "breach_amount": pytest.approx((90.0 / 200.0) - 0.2),
            "notes": None,
        },
    ]


def test_percent_of_total_scopes_denominator_to_matching_granularity() -> None:
    exposures = [
        {
            _LIMIT_GRANULARITY_KEY: _COUNTERPARTY_GRANULARITY,
            "counterparty": "Alpha",
            "notional": 600.0,
        },
        {
            _LIMIT_GRANULARITY_KEY: _COUNTERPARTY_GRANULARITY,
            "counterparty": "Beta",
            "notional": 400.0,
        },
        {
            _LIMIT_GRANULARITY_KEY: _FUTURES_GRANULARITY,
            "clearing_house": "CME",
            "segment": "Rates",
            "notional": 40.0,
        },
        {
            _LIMIT_GRANULARITY_KEY: _FUTURES_GRANULARITY,
            "clearing_house": "ICE",
            "segment": "Credit",
            "notional": 60.0,
        },
    ]
    limits_cfg = {
        "schema_version": 1,
        "limits": [
            {
                "entity_type": "clearing_house",
                "entity_name": "CME",
                "limit_value": 0.35,
                "limit_kind": "percent_of_total",
            }
        ],
    }

    rows = _as_records(check_limits(exposures, limits_cfg))

    assert rows == [
        {
            "entity_type": "clearing_house",
            "entity_name": "cme",
            "limit_kind": "percent_of_total",
            "severity": "warning",
            "actual_value": pytest.approx(0.4),
            "limit_value": 0.35,
            "breach_amount": pytest.approx(0.05),
            "notes": None,
        }
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
    assert (
        lines[0]
        == "entity_type,entity_name,limit_kind,severity,actual_value,limit_value,breach_amount,notes"
    )
    assert "counterparty,a,absolute_notional,warning,11.0,10.0,1.0," in lines[1:]


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


def test_check_limits_skips_disabled_limits_for_breaches_and_missing_entities() -> None:
    exposures = [{"counterparty": "A", "notional": 25.0}]
    limits_cfg = {
        "schema_version": 1,
        "limits": [
            {
                "entity_type": "counterparty",
                "entity_name": "A",
                "limit_value": 10.0,
                "limit_kind": "absolute_notional",
                "enabled": False,
            },
            {
                "entity_type": "counterparty",
                "entity_name": "Missing",
                "limit_value": 10.0,
                "limit_kind": "absolute_notional",
                "enabled": False,
            },
        ],
    }

    assert _as_records(check_limits(exposures, limits_cfg)) == []
    assert find_missing_limit_entities(exposures, limits_cfg) == []
