from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from counter_risk.renderers import render_cprs_fcm_png
from counter_risk.renderers.table_png import render_cprs_ch_png

_REQUIRED_ROW = {
    "Counterparty": "Alpha Clearing",
    "Cash": 125.0,
    "TIPS": 19.5,
    "Treasury": 302.25,
    "Equity": -15.0,
    "Commodity": 8.5,
    "Currency": 1.2,
    "Notional": 441.45,
}

_MIN_ROWS_BY_VARIANT = {
    "all_programs": 3,
    "ex_trend": 2,
    "trend": 1,
}


class _FakeDataFrame:
    def __init__(self, rows: list[dict[str, object]], columns: list[str] | None = None) -> None:
        self._rows = [dict(row) for row in rows]
        self.columns = (
            list(columns) if columns is not None else list(rows[0].keys()) if rows else []
        )

    def to_dict(self, orient: str = "dict") -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError("only records orient is supported")
        return [dict(row) for row in self._rows]


def _frame_for_variant(variant: str) -> _FakeDataFrame:
    return _FakeDataFrame([dict(_REQUIRED_ROW) for _ in range(_MIN_ROWS_BY_VARIANT[variant])])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_render_cprs_fcm_png_is_importable_from_renderers_package() -> None:
    assert callable(render_cprs_fcm_png)


def test_render_cprs_fcm_png_and_ch_png_route_through_shared_internal_helper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[object, Path | str, str | None]] = []

    def _fake_helper(
        exposures_df: object,
        output_png: Path | str,
        *,
        layout: object,
        variant: str | None = None,
        min_rows_by_variant: dict[str, int] | None = None,
    ) -> None:
        _ = (layout, min_rows_by_variant)
        calls.append((exposures_df, output_png, variant))

    monkeypatch.setattr("counter_risk.renderers.table_png._render_cprs_table_png", _fake_helper)

    frame = _frame_for_variant("all_programs")
    render_cprs_ch_png(frame, tmp_path / "ch.png", variant="all_programs")
    render_cprs_fcm_png(frame, tmp_path / "fcm.png", variant="all_programs")

    assert len(calls) == 2
    assert calls[0][2] == "all_programs"
    assert calls[1][2] == "all_programs"


@pytest.mark.parametrize("variant", ("all_programs", "ex_trend", "trend"))
def test_render_cprs_ch_png_writes_png_file_for_each_variant(tmp_path: Path, variant: str) -> None:
    output_path = tmp_path / f"ch-{variant}.png"
    render_cprs_ch_png(_frame_for_variant(variant), output_path, variant=variant)
    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.mark.parametrize("variant", ("all_programs", "ex_trend", "trend"))
def test_render_cprs_fcm_png_writes_png_file_for_each_variant(tmp_path: Path, variant: str) -> None:
    output_path = tmp_path / f"fcm-{variant}.png"
    render_cprs_fcm_png(_frame_for_variant(variant), output_path, variant=variant)
    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.mark.parametrize("variant", ("all_programs", "ex_trend", "trend"))
def test_render_cprs_ch_png_is_deterministic_for_each_variant(tmp_path: Path, variant: str) -> None:
    output_one = tmp_path / f"ch-{variant}-one.png"
    output_two = tmp_path / f"ch-{variant}-two.png"
    frame = _frame_for_variant(variant)

    render_cprs_ch_png(frame, output_one, variant=variant)
    render_cprs_ch_png(frame, output_two, variant=variant)

    assert _sha256(output_one) == _sha256(output_two)


@pytest.mark.parametrize("variant", ("all_programs", "ex_trend", "trend"))
def test_render_cprs_fcm_png_is_deterministic_for_each_variant(
    tmp_path: Path, variant: str
) -> None:
    output_one = tmp_path / f"fcm-{variant}-one.png"
    output_two = tmp_path / f"fcm-{variant}-two.png"
    frame = _frame_for_variant(variant)

    render_cprs_fcm_png(frame, output_one, variant=variant)
    render_cprs_fcm_png(frame, output_two, variant=variant)

    assert _sha256(output_one) == _sha256(output_two)


def test_render_cprs_ch_png_raises_on_none_exposures_df(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exposures_df"):
        render_cprs_ch_png(None, tmp_path / "ch-none.png")


def test_render_cprs_ch_png_raises_on_empty_dataframe(tmp_path: Path) -> None:
    columns = list(_REQUIRED_ROW.keys())
    with pytest.raises(ValueError, match="empty"):
        render_cprs_ch_png(_FakeDataFrame([], columns=columns), tmp_path / "ch-empty.png")


@pytest.mark.parametrize(
    ("variant", "row_count", "expected_min_rows"),
    (
        ("all_programs", 2, 3),
        ("ex_trend", 1, 2),
        ("trend", 0, 1),
    ),
)
def test_render_cprs_ch_png_raises_on_below_minimum_rows(
    tmp_path: Path, variant: str, row_count: int, expected_min_rows: int
) -> None:
    frame = _FakeDataFrame([dict(_REQUIRED_ROW) for _ in range(row_count)])
    with pytest.raises(ValueError, match=rf"rows?.*{expected_min_rows}"):
        render_cprs_ch_png(frame, tmp_path / f"ch-{variant}-few-rows.png", variant=variant)


def test_render_cprs_ch_png_raises_on_blank_counterparty(tmp_path: Path) -> None:
    frame = _frame_for_variant("all_programs")
    frame._rows[0]["Counterparty"] = "   "
    with pytest.raises(ValueError, match="counterparty"):
        render_cprs_ch_png(frame, tmp_path / "ch-blank-counterparty.png", variant="all_programs")


def test_render_cprs_fcm_png_raises_on_none_exposures_df(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exposures_df"):
        render_cprs_fcm_png(None, tmp_path / "fcm-none.png")


def test_render_cprs_fcm_png_raises_on_empty_dataframe(tmp_path: Path) -> None:
    columns = list(_REQUIRED_ROW.keys())
    with pytest.raises(ValueError, match="empty"):
        render_cprs_fcm_png(_FakeDataFrame([], columns=columns), tmp_path / "fcm-empty.png")


@pytest.mark.parametrize(
    ("variant", "row_count", "expected_min_rows"),
    (
        ("all_programs", 2, 3),
        ("ex_trend", 1, 2),
        ("trend", 0, 1),
    ),
)
def test_render_cprs_fcm_png_raises_on_below_minimum_rows(
    tmp_path: Path, variant: str, row_count: int, expected_min_rows: int
) -> None:
    frame = _FakeDataFrame([dict(_REQUIRED_ROW) for _ in range(row_count)])
    with pytest.raises(ValueError, match=rf"rows?.*{expected_min_rows}"):
        render_cprs_fcm_png(frame, tmp_path / f"fcm-{variant}-few-rows.png", variant=variant)


def test_render_cprs_fcm_png_raises_on_blank_counterparty(tmp_path: Path) -> None:
    frame = _frame_for_variant("all_programs")
    frame._rows[0]["Counterparty"] = "   "
    with pytest.raises(ValueError, match="counterparty"):
        render_cprs_fcm_png(frame, tmp_path / "fcm-blank-counterparty.png", variant="all_programs")
