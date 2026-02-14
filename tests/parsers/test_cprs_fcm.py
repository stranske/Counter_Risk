"""Tests for CPRS-FCM parser."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import pandas as pd  # type: ignore[import-untyped]
    from pandas.testing import assert_frame_equal  # type: ignore[import-untyped]
except ModuleNotFoundError:  # pragma: no cover - depends on test environment
    pd = None
    assert_frame_equal = None

from counter_risk.parsers.cprs_fcm import parse_fcm_totals, parse_futures_detail
from tests.utils.assertions import assert_numeric_outputs_close

_ALL_PROGRAMS_FIXTURE = "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx"
_EX_TREND_FIXTURE = "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx"
_TREND_FIXTURE = "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx"

_TOTAL_COLUMNS = (
    "counterparty",
    "TIPS",
    "Treasury",
    "Equity",
    "Commodity",
    "Currency",
    "Notional",
    "NotionalChange",
)

_FUTURES_COLUMNS = ("account", "description", "class", "fcm", "clearing_house", "notional")


def _fixture(name: str) -> Path:
    return Path("tests/fixtures") / name


def _empty_totals_frame() -> pd.DataFrame:
    _require_pandas()
    return pd.DataFrame(columns=_TOTAL_COLUMNS).astype(
        {
            "counterparty": "string",
            "TIPS": "float64",
            "Treasury": "float64",
            "Equity": "float64",
            "Commodity": "float64",
            "Currency": "float64",
            "Notional": "float64",
            "NotionalChange": "float64",
        }
    )


def _empty_futures_frame() -> pd.DataFrame:
    _require_pandas()
    return pd.DataFrame(columns=_FUTURES_COLUMNS).astype(
        {
            "account": "string",
            "description": "string",
            "class": "string",
            "fcm": "string",
            "clearing_house": "string",
            "notional": "float64",
        }
    )


def test_parse_fcm_totals_all_programs_non_empty_and_stable_columns() -> None:
    _require_pandas()
    df = parse_fcm_totals(_fixture(_ALL_PROGRAMS_FIXTURE))

    assert_frame_equal(df, df.loc[:, list(_TOTAL_COLUMNS)], check_like=False)
    assert not df.empty
    assert df["counterparty"].eq("Morgan Stanley").any()


def test_parse_fcm_totals_ex_trend_non_empty_and_stable_columns() -> None:
    _require_pandas()
    df = parse_fcm_totals(_fixture(_EX_TREND_FIXTURE))

    assert_frame_equal(df, df.loc[:, list(_TOTAL_COLUMNS)], check_like=False)
    assert not df.empty
    assert df["counterparty"].str.len().gt(0).all()


def test_parse_fcm_totals_all_programs_fixture_numeric_totals_close() -> None:
    _require_pandas()
    df = parse_fcm_totals(_fixture(_ALL_PROGRAMS_FIXTURE))

    totals = (
        df[["TIPS", "Treasury", "Equity", "Commodity", "Currency", "Notional", "NotionalChange"]]
        .sum()
        .to_dict()
    )
    expected_totals = {
        "TIPS": 613563453.14,
        "Treasury": 2437132088.31,
        "Equity": 4647960361.939,
        "Commodity": 124181574.6156,
        "Currency": -10837843.75,
        "Notional": 7811999634.2546,
        "NotionalChange": 13704178.2738,
    }
    assert_numeric_outputs_close(
        totals,
        expected_totals,
        abs_tol=1e-6,
        rel_tol=1e-12,
    )


def test_parse_fcm_totals_ex_trend_fixture_numeric_totals_close() -> None:
    _require_pandas()
    df = parse_fcm_totals(_fixture(_EX_TREND_FIXTURE))

    totals = (
        df[["TIPS", "Treasury", "Equity", "Commodity", "Currency", "Notional", "NotionalChange"]]
        .sum()
        .to_dict()
    )
    expected_totals = {
        "TIPS": 613563453.14,
        "Treasury": 2422820068.71,
        "Equity": 4578574679.329,
        "Commodity": 124131536.3156,
        "Currency": 0.0,
        "Notional": 7739089737.494599,
        "NotionalChange": 224224528.0238,
    }
    assert_numeric_outputs_close(
        totals,
        expected_totals,
        abs_tol=1e-6,
        rel_tol=1e-12,
    )


def test_parse_fcm_totals_trend_is_empty() -> None:
    _require_pandas()
    df = parse_fcm_totals(_fixture(_TREND_FIXTURE))

    assert_frame_equal(df, _empty_totals_frame())


def test_parse_futures_detail_all_programs_non_empty_and_stable_columns() -> None:
    _require_pandas()
    df = parse_futures_detail(_fixture(_ALL_PROGRAMS_FIXTURE))

    assert_frame_equal(df, df.loc[:, list(_FUTURES_COLUMNS)], check_like=False)
    assert not df.empty
    assert df["fcm"].eq("Morgan Stanley").all()


def test_parse_futures_detail_ex_trend_is_empty() -> None:
    _require_pandas()
    df = parse_futures_detail(_fixture(_EX_TREND_FIXTURE))

    assert_frame_equal(df, _empty_futures_frame())


def test_parse_futures_detail_trend_non_empty_and_stable_columns() -> None:
    _require_pandas()
    df = parse_futures_detail(_fixture(_TREND_FIXTURE))

    assert_frame_equal(df, df.loc[:, list(_FUTURES_COLUMNS)], check_like=False)
    assert not df.empty
    assert df["class"].eq("Currency").any()


@pytest.mark.parametrize("fixture_name", [_ALL_PROGRAMS_FIXTURE, _EX_TREND_FIXTURE, _TREND_FIXTURE])
def test_parse_fcm_totals_returns_dataframe_with_expected_dtypes(fixture_name: str) -> None:
    _require_pandas()
    df = parse_fcm_totals(_fixture(fixture_name))

    assert isinstance(df, pd.DataFrame)
    assert_frame_equal(
        df.dtypes.to_frame(name="dtype"), _empty_totals_frame().dtypes.to_frame(name="dtype")
    )


@pytest.mark.parametrize("fixture_name", [_ALL_PROGRAMS_FIXTURE, _EX_TREND_FIXTURE, _TREND_FIXTURE])
def test_parse_futures_detail_returns_dataframe_with_expected_dtypes(fixture_name: str) -> None:
    _require_pandas()
    df = parse_futures_detail(_fixture(fixture_name))

    assert isinstance(df, pd.DataFrame)
    assert_frame_equal(
        df.dtypes.to_frame(name="dtype"),
        _empty_futures_frame().dtypes.to_frame(name="dtype"),
    )


def _require_pandas() -> None:
    if pd is None or assert_frame_equal is None:
        pytest.skip("pandas is required for CPRS-FCM parser DataFrame tests")
