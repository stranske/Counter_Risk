"""Tests for deterministic CPRS-CH PNG rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.renderers.table_png import (
    cprs_ch_font_spec,
    cprs_ch_render_backend,
    cprs_ch_render_backend_notes,
    cprs_ch_table_columns,
    cprs_ch_table_header_layout,
    cprs_ch_table_headers,
    cprs_ch_table_layout,
    cprs_ch_table_style,
    cprs_ch_view_spec,
    render_cprs_ch_png,
)


class _FakeDataFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = [dict(row) for row in rows]
        self.columns = list(rows[0].keys()) if rows else []

    def to_dict(self, orient: str = "dict") -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError("only records orient is supported")
        return [dict(row) for row in self._rows]


_REQUIRED = {
    "Counterparty": "Alpha Clearing",
    "Cash": 125.0,
    "TIPS": 19.5,
    "Treasury": 302.25,
    "Equity": -15.0,
    "Commodity": 8.5,
    "Currency": 1.2,
    "Notional": 441.45,
}


def _sample_frame() -> _FakeDataFrame:
    return _FakeDataFrame(
        [
            _REQUIRED,
            {
                "Counterparty": "Beta FCM",
                "Cash": 7,
                "TIPS": 0,
                "Treasury": 10,
                "Equity": 2,
                "Commodity": 3,
                "Currency": 4,
                "Notional": 26,
            },
        ]
    )


def test_render_cprs_ch_png_writes_deterministic_bytes(tmp_path: Path) -> None:
    output_one = tmp_path / "first.png"
    output_two = tmp_path / "second.png"

    render_cprs_ch_png(_sample_frame(), output_one)
    render_cprs_ch_png(_sample_frame(), output_two)

    data_one = output_one.read_bytes()
    data_two = output_two.read_bytes()

    assert data_one.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(data_one) > 500
    assert data_one == data_two


def test_render_cprs_ch_png_missing_required_columns_raises(tmp_path: Path) -> None:
    output = tmp_path / "missing.png"
    bad = _FakeDataFrame([{"Counterparty": "Only", "Cash": 1.0}])

    with pytest.raises(ValueError, match="missing required columns"):
        render_cprs_ch_png(bad, output)


def test_render_cprs_ch_png_malformed_numeric_value_raises(tmp_path: Path) -> None:
    output = tmp_path / "bad-value.png"
    bad = _sample_frame()
    bad._rows[0]["Cash"] = "not-a-number"

    with pytest.raises(ValueError, match="non-numeric value"):
        render_cprs_ch_png(bad, output)


def test_cprs_ch_table_columns_are_stable() -> None:
    assert cprs_ch_table_columns() == (
        "Counterparty",
        "Cash",
        "TIPS",
        "Treasury",
        "Equity",
        "Commodity",
        "Currency",
        "Notional",
    )


def test_cprs_ch_table_headers_are_stable() -> None:
    assert cprs_ch_table_headers() == (
        "Counterparty",
        "Cash",
        "TIPS",
        "Treasury",
        "Equity",
        "Commodity",
        "Currency",
        "Notional",
    )


def test_cprs_ch_table_layout_contract_is_stable() -> None:
    assert cprs_ch_table_layout() == (
        {
            "key": "Counterparty",
            "header": "Counterparty",
            "width_chars": 28,
            "header_align": "left",
        },
        {"key": "Cash", "header": "Cash", "width_chars": 11, "header_align": "right"},
        {"key": "TIPS", "header": "TIPS", "width_chars": 10, "header_align": "right"},
        {
            "key": "Treasury",
            "header": "Treasury",
            "width_chars": 12,
            "header_align": "right",
        },
        {"key": "Equity", "header": "Equity", "width_chars": 10, "header_align": "right"},
        {
            "key": "Commodity",
            "header": "Commodity",
            "width_chars": 12,
            "header_align": "right",
        },
        {
            "key": "Currency",
            "header": "Currency",
            "width_chars": 11,
            "header_align": "right",
        },
        {
            "key": "Notional",
            "header": "Notional",
            "width_chars": 12,
            "header_align": "right",
        },
    )


def test_cprs_ch_table_header_layout_contract_is_stable() -> None:
    assert cprs_ch_table_header_layout() == (
        {"key": "Counterparty", "header": "Counterparty", "header_align": "left"},
        {"key": "Cash", "header": "Cash", "header_align": "right"},
        {"key": "TIPS", "header": "TIPS", "header_align": "right"},
        {"key": "Treasury", "header": "Treasury", "header_align": "right"},
        {"key": "Equity", "header": "Equity", "header_align": "right"},
        {"key": "Commodity", "header": "Commodity", "header_align": "right"},
        {"key": "Currency", "header": "Currency", "header_align": "right"},
        {"key": "Notional", "header": "Notional", "header_align": "right"},
    )


def test_cprs_ch_render_backend_is_explicit_and_stable() -> None:
    assert cprs_ch_render_backend() == "internal_pure_python_png_encoder"


def test_cprs_ch_render_backend_notes_document_library_choice() -> None:
    notes = cprs_ch_render_backend_notes()
    assert "pure-Python PNG encoder" in notes
    assert "deterministic" in notes


def test_cprs_ch_font_spec_is_explicit_and_stable() -> None:
    assert cprs_ch_font_spec() == {
        "family": "builtin_5x7_bitmap",
        "glyph_width_px": 10,
        "glyph_height_px": 14,
        "glyph_gap_px": 2,
    }


def test_cprs_ch_table_style_is_explicit_and_stable() -> None:
    assert cprs_ch_table_style() == {
        "background": (255, 255, 255),
        "header_background": (29, 50, 90),
        "header_text": (255, 255, 255),
        "grid": (178, 187, 203),
        "alternate_row_background": (242, 246, 252),
        "text": (26, 26, 26),
    }


def test_cprs_ch_view_spec_documents_library_and_styling() -> None:
    spec = cprs_ch_view_spec()
    assert spec["render_backend"] == "internal_pure_python_png_encoder"
    assert "pure-Python PNG encoder" in str(spec["render_backend_notes"])
    assert spec["font"] == cprs_ch_font_spec()
    assert spec["columns"] == cprs_ch_table_columns()
    assert spec["headers"] == cprs_ch_table_headers()
    assert spec["layout"] == cprs_ch_table_layout()
    assert spec["header_layout"] == cprs_ch_table_header_layout()
    assert spec["style"] == cprs_ch_table_style()
