"""Tests for deterministic CPRS-CH PNG rendering."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from counter_risk.renderers import table_png
from counter_risk.renderers.table_png import (
    _to_renderable_rows,
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
    render_cprs_fcm_png,
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


@pytest.mark.parametrize("renderer_name", ("render_cprs_ch_png", "render_cprs_fcm_png"))
@pytest.mark.parametrize("profile", ("plain", "currency", "accounting"))
def test_numeric_cell_text_right_alignment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, renderer_name: str, profile: str
) -> None:
    calls: list[tuple[int, str]] = []
    original_draw_text = table_png._draw_text

    def record_text(
        pixels: bytearray, width: int, x: int, y: int, text: str, color: table_png.RGB
    ) -> None:
        calls.append((x, text))
        original_draw_text(pixels, width, x, y, text, color)

    monkeypatch.setattr(table_png, "_draw_text", record_text)
    getattr(table_png, renderer_name)(
        _sample_frame(), tmp_path / "aligned.png", formatting_profile=profile
    )

    columns = cprs_ch_table_layout()
    assert len(calls) == 3 * len(columns)  # Header and two rows of differing numeric widths.
    cell_left = 12
    for index, column in enumerate(columns):
        cell_width = table_png._column_pixel_width(int(column["width_chars"]))
        for row_index in range(3):
            text_x, text = calls[row_index * len(columns) + index]
            if index == 0:
                assert text_x == cell_left + table_png._CELL_PADDING_X
            else:
                assert (
                    text_x + table_png._text_pixel_width(text)
                    == cell_left + cell_width - table_png._CELL_PADDING_X
                )
        cell_left += cell_width + 1


@pytest.mark.parametrize("renderer_name", ("render_cprs_ch_png", "render_cprs_fcm_png"))
def test_numeric_cell_png_right_alignment(tmp_path: Path, renderer_name: str) -> None:
    output = tmp_path / "aligned.png"
    getattr(table_png, renderer_name)(_sample_frame(), output)
    png = output.read_bytes()
    width, height = struct.unpack(">II", png[16:24])
    compressed = bytearray()
    offset = 8
    while offset < len(png):
        length = int.from_bytes(png[offset : offset + 4], "big")
        if png[offset + 4 : offset + 8] == b"IDAT":
            compressed.extend(png[offset + 8 : offset + 8 + length])
        offset += length + 12
    scanlines = zlib.decompress(compressed)
    stride = width * 3 + 1
    assert len(scanlines) == height * stride
    assert all(scanlines[y * stride] == 0 for y in range(height))

    row_height = table_png._CHAR_HEIGHT + 2 * table_png._CELL_PADDING_Y
    cell_left = 12
    for index, column in enumerate(cprs_ch_table_layout()):
        cell_width = table_png._column_pixel_width(int(column["width_chars"]))
        for row_index in range(3):
            top = 12 + row_index * (row_height + 1) + table_png._CELL_PADDING_Y
            color = bytes(cprs_ch_table_style()["header_text" if row_index == 0 else "text"])
            ink_x = [
                x
                for y in range(top, top + table_png._CHAR_HEIGHT)
                for x in range(cell_left, cell_left + cell_width)
                if scanlines[y * stride + 1 + x * 3 : y * stride + 1 + x * 3 + 3] == color
            ]
            assert ink_x
            if index == 0:
                assert min(ink_x) == cell_left + table_png._CELL_PADDING_X
            else:
                assert max(ink_x) == cell_left + cell_width - table_png._CELL_PADDING_X - 1
        cell_left += cell_width + 1


def test_render_cprs_fcm_png_writes_deterministic_bytes(tmp_path: Path) -> None:
    output_one = tmp_path / "first-fcm.png"
    output_two = tmp_path / "second-fcm.png"

    render_cprs_fcm_png(_sample_frame(), output_one)
    render_cprs_fcm_png(_sample_frame(), output_two)

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


def test_render_cprs_ch_png_empty_dataframe_raises(tmp_path: Path) -> None:
    output = tmp_path / "empty.png"

    with pytest.raises(ValueError, match="empty DataFrame"):
        render_cprs_ch_png(_FakeDataFrame([]), output)


def test_render_cprs_ch_png_none_exposures_df_raises(tmp_path: Path) -> None:
    output = tmp_path / "none.png"

    with pytest.raises(ValueError, match="exposures_df"):
        render_cprs_ch_png(None, output)


@pytest.mark.parametrize(
    ("variant", "row_count", "expected_rows"),
    (
        ("all_programs", 2, 3),
        ("ex_trend", 1, 2),
        ("trend", 0, 1),
    ),
)
def test_render_cprs_ch_png_below_minimum_rows_raises(
    tmp_path: Path, variant: str, row_count: int, expected_rows: int
) -> None:
    output = tmp_path / f"{variant}-rows.png"
    frame = _FakeDataFrame([dict(_REQUIRED) for _ in range(row_count)])

    with pytest.raises(ValueError, match=r"rows?"):
        render_cprs_ch_png(frame, output, variant=variant)

    with pytest.raises(ValueError, match=str(expected_rows)):
        render_cprs_ch_png(frame, output, variant=variant)


def test_render_cprs_ch_png_malformed_numeric_value_raises(tmp_path: Path) -> None:
    output = tmp_path / "bad-value.png"
    bad = _sample_frame()
    bad._rows[0]["Cash"] = "not-a-number"

    with pytest.raises(ValueError, match="non-numeric value"):
        render_cprs_ch_png(bad, output)


def test_to_renderable_rows_formats_currency_profile_with_symbol() -> None:
    rows = _to_renderable_rows(_sample_frame(), formatting_profile="currency")

    assert rows[0]["Cash"] == "$125.00"
    assert rows[0]["Equity"] == "-$15.00"


def test_to_renderable_rows_formats_accounting_profile_with_parentheses() -> None:
    rows = _to_renderable_rows(_sample_frame(), formatting_profile="accounting")

    assert rows[0]["Cash"] == "$125.00"
    assert rows[0]["Equity"] == "($15.00)"


@pytest.mark.parametrize("character", ("$", "(", ")"))
def test_currency_and_accounting_glyphs_have_explicit_bitmaps(character: str) -> None:
    glyph = table_png._glyph_for(character)

    assert isinstance(glyph, tuple)
    assert glyph == table_png._GLYPHS[character]
    assert glyph != table_png._GLYPHS["?"]
    assert len(glyph) == 7
    assert all(len(row) == 5 and set(row) <= {"0", "1"} for row in glyph)
    assert any("1" in row for row in glyph)


@pytest.mark.parametrize("renderer_name", ("render_cprs_ch_png", "render_cprs_fcm_png"))
@pytest.mark.parametrize(
    ("profile", "expected_symbols"), (("currency", {"$", "-"}), ("accounting", {"$", "(", ")"}))
)
def test_formatted_table_pngs_render_without_fallback_glyphs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    renderer_name: str,
    profile: str,
    expected_symbols: set[str],
) -> None:
    original_glyph_for = table_png._glyph_for
    rendered_characters: set[str] = set()

    def checked_glyph_for(character: str) -> tuple[str, ...]:
        glyph = original_glyph_for(character)
        assert glyph != table_png._GLYPHS["?"], f"Fallback glyph for {character!r}"
        rendered_characters.add(character)
        return glyph

    monkeypatch.setattr(table_png, "_glyph_for", checked_glyph_for)
    output = tmp_path / f"{renderer_name}-{profile}.png"
    renderer = getattr(table_png, renderer_name)
    renderer(_sample_frame(), output, formatting_profile=profile)

    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert expected_symbols <= rendered_characters


def test_render_cprs_fcm_png_none_exposures_df_raises(tmp_path: Path) -> None:
    output = tmp_path / "none-fcm.png"

    with pytest.raises(ValueError, match="exposures_df"):
        render_cprs_fcm_png(None, output)


def test_render_cprs_fcm_png_empty_dataframe_raises(tmp_path: Path) -> None:
    output = tmp_path / "empty-fcm.png"

    with pytest.raises(ValueError, match="empty DataFrame"):
        render_cprs_fcm_png(_FakeDataFrame([]), output)


def test_render_cprs_fcm_png_missing_counterparty_column_raises(tmp_path: Path) -> None:
    output = tmp_path / "missing-counterparty-fcm.png"
    bad = _FakeDataFrame(
        [
            {
                "Cash": 125.0,
                "TIPS": 19.5,
                "Treasury": 302.25,
                "Equity": -15.0,
                "Commodity": 8.5,
                "Currency": 1.2,
                "Notional": 441.45,
            }
        ]
    )

    with pytest.raises(ValueError, match="counterparty"):
        render_cprs_fcm_png(bad, output)


@pytest.mark.parametrize(
    ("variant", "row_count", "expected_rows"),
    (
        ("all_programs", 2, 3),
        ("ex_trend", 1, 2),
        ("trend", 0, 1),
    ),
)
def test_render_cprs_fcm_png_below_minimum_rows_raises(
    tmp_path: Path, variant: str, row_count: int, expected_rows: int
) -> None:
    output = tmp_path / f"{variant}-fcm-rows.png"
    frame = _FakeDataFrame([dict(_REQUIRED) for _ in range(row_count)])

    with pytest.raises(ValueError, match=r"rows?"):
        render_cprs_fcm_png(frame, output, variant=variant)

    with pytest.raises(ValueError, match=str(expected_rows)):
        render_cprs_fcm_png(frame, output, variant=variant)


@pytest.mark.parametrize("counterparty_value", ("   ", None))
def test_render_cprs_ch_png_blank_counterparty_raises(
    tmp_path: Path, counterparty_value: object
) -> None:
    output = tmp_path / "blank-counterparty.png"
    bad = _sample_frame()
    bad._rows[0]["Counterparty"] = counterparty_value

    with pytest.raises(ValueError, match="counterparty"):
        render_cprs_ch_png(bad, output)


@pytest.mark.parametrize("counterparty_value", ("   ", None))
def test_render_cprs_fcm_png_blank_counterparty_raises(
    tmp_path: Path, counterparty_value: object
) -> None:
    output = tmp_path / "blank-counterparty-fcm.png"
    bad = _sample_frame()
    bad._rows[0]["Counterparty"] = counterparty_value

    with pytest.raises(ValueError, match="counterparty"):
        render_cprs_fcm_png(bad, output)


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
