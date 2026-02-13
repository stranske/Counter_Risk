"""Deterministic PNG renderers for screenshot replacement workflows.

Rendering library choice for CPRS-CH/CPRS-FCM table output is explicitly:
``internal_pure_python_png_encoder``.
This renderer intentionally uses an internal pure-Python PNG encoder and bitmap
glyph table (instead of PIL/matplotlib) so output bytes are stable across
machines and runtime environments.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

RGB = tuple[int, int, int]

_SCALE = 2
_CELL_PADDING_X = 5
_CELL_PADDING_Y = 4
_CHAR_WIDTH = 5 * _SCALE
_CHAR_HEIGHT = 7 * _SCALE
_CHAR_GAP = 1 * _SCALE


@dataclass(frozen=True)
class _TableColumn:
    key: str
    header: str
    width_chars: int
    header_align: str


@dataclass(frozen=True)
class _TableStyle:
    background: RGB
    header_background: RGB
    header_text: RGB
    grid: RGB
    alternate_row_background: RGB
    text: RGB


@dataclass(frozen=True)
class _TableLayout:
    columns: tuple[_TableColumn, ...]
    style: _TableStyle


@dataclass(frozen=True)
class _BitmapFont:
    family: str
    glyph_width_px: int
    glyph_height_px: int
    glyph_gap_px: int


_TABLE_COLUMNS: tuple[_TableColumn, ...] = (
    _TableColumn("Counterparty", "Counterparty", 28, "left"),
    _TableColumn("Cash", "Cash", 11, "right"),
    _TableColumn("TIPS", "TIPS", 10, "right"),
    _TableColumn("Treasury", "Treasury", 12, "right"),
    _TableColumn("Equity", "Equity", 10, "right"),
    _TableColumn("Commodity", "Commodity", 12, "right"),
    _TableColumn("Currency", "Currency", 11, "right"),
    _TableColumn("Notional", "Notional", 12, "right"),
)

_CPRS_CH_STYLE = _TableStyle(
    background=(255, 255, 255),
    header_background=(29, 50, 90),
    header_text=(255, 255, 255),
    grid=(178, 187, 203),
    alternate_row_background=(242, 246, 252),
    text=(26, 26, 26),
)
_CPRS_CH_LAYOUT = _TableLayout(columns=_TABLE_COLUMNS, style=_CPRS_CH_STYLE)

_REQUIRED_COLUMNS = {column.key for column in _TABLE_COLUMNS}
_CPRS_CH_RENDER_BACKEND = "internal_pure_python_png_encoder"
_CPRS_MIN_ROWS_BY_VARIANT: dict[str, int] = {
    "all_programs": 3,
    "ex_trend": 2,
    "trend": 1,
}
_CPRS_CH_FONT = _BitmapFont(
    family="builtin_5x7_bitmap",
    glyph_width_px=_CHAR_WIDTH,
    glyph_height_px=_CHAR_HEIGHT,
    glyph_gap_px=_CHAR_GAP,
)


def cprs_ch_table_columns() -> tuple[str, ...]:
    """Return the deterministic CPRS-CH column order used for PNG rendering."""
    return tuple(column.key for column in _TABLE_COLUMNS)


def cprs_ch_table_headers() -> tuple[str, ...]:
    """Return the deterministic CPRS-CH header labels used in the PNG table."""
    return tuple(column.header for column in _TABLE_COLUMNS)


def cprs_ch_table_layout() -> tuple[dict[str, str | int], ...]:
    """Return the deterministic CPRS-CH column layout contract for PNG rendering."""
    return tuple(
        {
            "key": column.key,
            "header": column.header,
            "width_chars": column.width_chars,
            "header_align": column.header_align,
        }
        for column in _TABLE_COLUMNS
    )


def cprs_ch_table_header_layout() -> tuple[dict[str, str], ...]:
    """Return the deterministic CPRS-CH header layout used in the PNG table."""
    return tuple(
        {
            "key": column.key,
            "header": column.header,
            "header_align": column.header_align,
        }
        for column in _TABLE_COLUMNS
    )


def cprs_ch_render_backend() -> str:
    """Return the rendering backend selected for deterministic CPRS-CH PNGs."""
    return _CPRS_CH_RENDER_BACKEND


def cprs_ch_render_backend_notes() -> str:
    """Return an implementation note describing the selected rendering backend."""
    return (
        "Uses an internal pure-Python PNG encoder and builtin 5x7 bitmap glyphs "
        "for deterministic rendering without external image libraries."
    )


def cprs_ch_font_spec() -> dict[str, int | str]:
    """Return the deterministic CPRS-CH font contract used during rendering."""
    return {
        "family": _CPRS_CH_FONT.family,
        "glyph_width_px": _CPRS_CH_FONT.glyph_width_px,
        "glyph_height_px": _CPRS_CH_FONT.glyph_height_px,
        "glyph_gap_px": _CPRS_CH_FONT.glyph_gap_px,
    }


def cprs_ch_table_style() -> dict[str, RGB]:
    """Return the CPRS-CH table style contract used during rendering."""
    return {
        "background": _CPRS_CH_LAYOUT.style.background,
        "header_background": _CPRS_CH_LAYOUT.style.header_background,
        "header_text": _CPRS_CH_LAYOUT.style.header_text,
        "grid": _CPRS_CH_LAYOUT.style.grid,
        "alternate_row_background": _CPRS_CH_LAYOUT.style.alternate_row_background,
        "text": _CPRS_CH_LAYOUT.style.text,
    }


def cprs_ch_view_spec() -> dict[str, object]:
    """Return the full deterministic CPRS-CH rendering contract.

    This function documents the selected PNG rendering library and the
    table/view styling used for screenshot generation.
    """
    return {
        "render_backend": cprs_ch_render_backend(),
        "render_backend_notes": cprs_ch_render_backend_notes(),
        "font": cprs_ch_font_spec(),
        "columns": cprs_ch_table_columns(),
        "headers": cprs_ch_table_headers(),
        "layout": cprs_ch_table_layout(),
        "header_layout": cprs_ch_table_header_layout(),
        "style": cprs_ch_table_style(),
    }


def render_cprs_ch_png(
    exposures_df: object, output_png: Path | str, *, variant: str | None = None
) -> None:
    """Render a deterministic CPRS-CH table PNG."""
    _render_cprs_table_png(
        exposures_df,
        output_png,
        layout=_CPRS_CH_LAYOUT,
        variant=variant,
        min_rows_by_variant=_CPRS_MIN_ROWS_BY_VARIANT,
    )


def render_cprs_fcm_png(
    exposures_df: object, output_png: Path | str, *, variant: str | None = None
) -> None:
    """Render a deterministic CPRS-FCM table PNG."""
    _render_cprs_table_png(
        exposures_df,
        output_png,
        layout=_CPRS_CH_LAYOUT,
        variant=variant,
        min_rows_by_variant=_CPRS_MIN_ROWS_BY_VARIANT,
    )


def _render_cprs_table_png(
    exposures_df: object,
    output_png: Path | str,
    *,
    layout: _TableLayout,
    variant: str | None = None,
    min_rows_by_variant: dict[str, int] | None = None,
) -> None:
    rows = _to_renderable_rows(
        exposures_df,
        variant=variant,
        min_rows_by_variant=min_rows_by_variant,
    )
    destination = Path(output_png)
    destination.parent.mkdir(parents=True, exist_ok=True)

    col_widths = [_column_pixel_width(column.width_chars) for column in layout.columns]
    row_height = _CHAR_HEIGHT + (2 * _CELL_PADDING_Y)
    table_width = sum(col_widths) + len(col_widths) + 1
    table_height = (len(rows) + 1) * row_height + len(rows) + 2

    width = table_width + 24
    height = table_height + 24
    pixels = bytearray(width * height * 3)
    _fill_rect(pixels, width, 0, 0, width, height, layout.style.background)

    origin_x = 12
    origin_y = 12

    x = origin_x
    for col_index, column in enumerate(layout.columns):
        cell_width = col_widths[col_index]
        _fill_rect(
            pixels,
            width,
            x,
            origin_y,
            cell_width,
            row_height,
            layout.style.header_background,
        )
        text_x = x + _CELL_PADDING_X
        if column.header_align == "right":
            text_x = x + cell_width - _CELL_PADDING_X - _text_pixel_width(column.header)
        _draw_text(
            pixels,
            width,
            text_x,
            origin_y + _CELL_PADDING_Y,
            column.header,
            layout.style.header_text,
        )
        x += cell_width + 1

    for row_index, row in enumerate(rows):
        y = origin_y + row_height + 1 + row_index * (row_height + 1)
        if row_index % 2 == 1:
            _fill_rect(
                pixels,
                width,
                origin_x,
                y,
                table_width - 1,
                row_height,
                layout.style.alternate_row_background,
            )

        x = origin_x
        for column_index, column in enumerate(layout.columns):
            text = row[column.key]
            _draw_text(
                pixels,
                width,
                x + _CELL_PADDING_X,
                y + _CELL_PADDING_Y,
                text,
                layout.style.text,
            )
            x += col_widths[column_index] + 1

    _draw_grid(
        pixels,
        width,
        origin_x,
        origin_y,
        col_widths,
        row_height,
        len(rows),
        layout.style.grid,
    )
    png_bytes = _encode_png(width=width, height=height, rgb_data=bytes(pixels))
    destination.write_bytes(png_bytes)


def _to_renderable_rows(
    exposures_df: object,
    *,
    variant: str | None = None,
    min_rows_by_variant: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    records = _read_records(exposures_df)
    if variant is not None and min_rows_by_variant:
        normalized_variant = _normalize_variant_key(variant)
        expected_rows = min_rows_by_variant.get(normalized_variant)
        if expected_rows is None:
            supported = ", ".join(sorted(min_rows_by_variant))
            raise ValueError(f"unsupported variant '{variant}'; expected one of: {supported}")
        if len(records) < expected_rows:
            raise ValueError(
                "exposures_df has "
                f"{len(records)} rows for variant '{normalized_variant}'; "
                f"expected at least {expected_rows} rows"
            )

    if not records:
        raise ValueError("exposures_df is an empty DataFrame")

    columns = _read_columns(exposures_df)
    missing_columns = sorted(_REQUIRED_COLUMNS - set(columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"exposures_df is missing required columns: {missing}")

    rendered: list[dict[str, str]] = []
    for index, record in enumerate(records):
        normalized: dict[str, str] = {}
        for column in _TABLE_COLUMNS:
            value = record.get(column.key)
            if column.key == "Counterparty":
                if value is None or str(value).strip() == "":
                    raise ValueError(f"row {index} is missing a counterparty value")
                normalized[column.key] = str(value).strip()
                continue

            number = _coerce_number(value, row_index=index, column_name=column.key)
            normalized[column.key] = f"{number:,.2f}"
        rendered.append(normalized)

    return rendered


def _normalize_variant_key(variant: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "_" for ch in variant).strip("_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized


def _read_columns(exposures_df: object) -> list[str]:
    columns = getattr(exposures_df, "columns", None)
    if columns is None:
        raise ValueError("exposures_df must provide a columns attribute")
    return [str(column) for column in columns]


def _read_records(exposures_df: object) -> list[dict[str, object]]:
    if exposures_df is None:
        raise ValueError("exposures_df cannot be None")

    if hasattr(exposures_df, "to_dict"):
        try:
            records = exposures_df.to_dict(orient="records")
        except TypeError:
            records = exposures_df.to_dict("records")
        if isinstance(records, list):
            return [dict(record) for record in records]

    if hasattr(exposures_df, "to_records"):
        raw = exposures_df.to_records()
        return [dict(record) for record in raw]

    raise ValueError("exposures_df must provide to_dict(orient='records') or to_records()")


def _coerce_number(value: object, *, row_index: int, column_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"row {row_index} column {column_name} has invalid boolean value")
    try:
        numeric = (
            value if isinstance(value, (str, bytes, bytearray, int, float)) else cast(Any, value)
        )
        number = float(numeric)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"row {row_index} column {column_name} has non-numeric value: {value!r}"
        ) from exc

    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"row {row_index} column {column_name} has non-finite numeric value")
    return number


def _column_pixel_width(char_width: int) -> int:
    return char_width * (_CHAR_WIDTH + _CHAR_GAP) + (2 * _CELL_PADDING_X)


def _fill_rect(
    pixels: bytearray,
    image_width: int,
    x: int,
    y: int,
    rect_width: int,
    rect_height: int,
    color: RGB,
) -> None:
    r, g, b = color
    for row in range(y, y + rect_height):
        for col in range(x, x + rect_width):
            offset = ((row * image_width) + col) * 3
            pixels[offset] = r
            pixels[offset + 1] = g
            pixels[offset + 2] = b


def _draw_grid(
    pixels: bytearray,
    image_width: int,
    origin_x: int,
    origin_y: int,
    col_widths: list[int],
    row_height: int,
    row_count: int,
    grid_color: RGB,
) -> None:
    table_height = (row_count + 1) * row_height + row_count + 1
    table_width = sum(col_widths) + len(col_widths)

    # Outer border.
    _fill_rect(pixels, image_width, origin_x, origin_y, table_width, 1, grid_color)
    _fill_rect(
        pixels,
        image_width,
        origin_x,
        origin_y + table_height,
        table_width,
        1,
        grid_color,
    )
    _fill_rect(pixels, image_width, origin_x, origin_y, 1, table_height + 1, grid_color)
    _fill_rect(
        pixels,
        image_width,
        origin_x + table_width,
        origin_y,
        1,
        table_height + 1,
        grid_color,
    )

    # Inner row boundaries.
    for row in range(1, row_count + 1):
        y = origin_y + row * row_height + (row - 1)
        _fill_rect(pixels, image_width, origin_x, y, table_width + 1, 1, grid_color)

    # Inner column boundaries.
    x = origin_x
    for col_width in col_widths[:-1]:
        x += col_width + 1
        _fill_rect(pixels, image_width, x, origin_y, 1, table_height + 1, grid_color)


def _draw_text(
    pixels: bytearray,
    image_width: int,
    x: int,
    y: int,
    text: str,
    color: RGB,
) -> None:
    cursor = x
    for character in text:
        glyph = _glyph_for(character)
        _draw_glyph(pixels, image_width, cursor, y, glyph, color)
        cursor += _CHAR_WIDTH + _CHAR_GAP


def _text_pixel_width(text: str) -> int:
    if not text:
        return 0
    return (len(text) * (_CHAR_WIDTH + _CHAR_GAP)) - _CHAR_GAP


def _draw_glyph(
    pixels: bytearray,
    image_width: int,
    x: int,
    y: int,
    glyph: tuple[str, ...],
    color: RGB,
) -> None:
    for row_index, row in enumerate(glyph):
        for col_index, pixel in enumerate(row):
            if pixel != "1":
                continue
            px = x + (col_index * _SCALE)
            py = y + (row_index * _SCALE)
            _fill_rect(pixels, image_width, px, py, _SCALE, _SCALE, color)


def _glyph_for(char: str) -> tuple[str, ...]:
    mapped = _GLYPHS.get(char)
    if mapped is not None:
        return mapped
    fallback = _GLYPHS.get(char.upper())
    if fallback is not None:
        return fallback
    return _GLYPHS["?"]


def _encode_png(*, width: int, height: int, rgb_data: bytes) -> bytes:
    raw = bytearray()
    row_stride = width * 3
    for row in range(height):
        raw.append(0)
        start = row * row_stride
        raw.extend(rgb_data[start : start + row_stride])

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw), level=9)

    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", ihdr),
            _png_chunk(b"IDAT", idat),
            _png_chunk(b"IEND", b""),
        ]
    )


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc)
    crc_bytes = struct.pack(">I", crc & 0xFFFFFFFF)
    return length + chunk_type + data + crc_bytes


_GLYPHS: dict[str, tuple[str, ...]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    ",": ("00000", "00000", "00000", "00000", "00110", "00100", "01000"),
    "/": ("00001", "00010", "00100", "01000", "10000", "00000", "00000"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "10000", "10000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00001", "00001", "00001", "00001", "10001", "10001", "01110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10001", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10001", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "?": ("01110", "10001", "00010", "00100", "00100", "00000", "00100"),
}
