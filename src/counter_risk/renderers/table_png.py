"""Deterministic PNG renderers for screenshot replacement workflows."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any, cast

RGB = tuple[int, int, int]

_COLOR_BACKGROUND: RGB = (255, 255, 255)
_COLOR_HEADER_BG: RGB = (29, 50, 90)
_COLOR_HEADER_TEXT: RGB = (255, 255, 255)
_COLOR_GRID: RGB = (178, 187, 203)
_COLOR_ROW_ALT: RGB = (242, 246, 252)
_COLOR_TEXT: RGB = (26, 26, 26)

_SCALE = 2
_CELL_PADDING_X = 5
_CELL_PADDING_Y = 4
_CHAR_WIDTH = 5 * _SCALE
_CHAR_HEIGHT = 7 * _SCALE
_CHAR_GAP = 1 * _SCALE

_TABLE_COLUMNS: tuple[tuple[str, str, int], ...] = (
    ("Counterparty", "Counterparty", 28),
    ("Cash", "Cash", 11),
    ("TIPS", "TIPS", 10),
    ("Treasury", "Treasury", 12),
    ("Equity", "Equity", 10),
    ("Commodity", "Commodity", 12),
    ("Currency", "Currency", 11),
    ("Notional", "Notional", 12),
)

_REQUIRED_COLUMNS = {column for column, _, _ in _TABLE_COLUMNS}


def render_cprs_ch_png(exposures_df: object, output_png: Path | str) -> None:
    """Render a deterministic CPRS-CH table PNG.

    The table layout is stable across runs and uses a built-in bitmap font to avoid
    environment-specific font differences.
    """

    rows = _to_renderable_rows(exposures_df)
    destination = Path(output_png)
    destination.parent.mkdir(parents=True, exist_ok=True)

    col_widths = [_column_pixel_width(char_width) for _, _, char_width in _TABLE_COLUMNS]
    row_height = _CHAR_HEIGHT + (2 * _CELL_PADDING_Y)
    table_width = sum(col_widths) + len(col_widths) + 1
    table_height = (len(rows) + 1) * row_height + len(rows) + 2

    width = table_width + 24
    height = table_height + 24
    pixels = bytearray(width * height * 3)
    _fill_rect(pixels, width, 0, 0, width, height, _COLOR_BACKGROUND)

    origin_x = 12
    origin_y = 12

    x = origin_x
    for col_index, (_, header, _) in enumerate(_TABLE_COLUMNS):
        cell_width = col_widths[col_index]
        _fill_rect(pixels, width, x, origin_y, cell_width, row_height, _COLOR_HEADER_BG)
        _draw_text(
            pixels,
            width,
            x + _CELL_PADDING_X,
            origin_y + _CELL_PADDING_Y,
            header,
            _COLOR_HEADER_TEXT,
        )
        x += cell_width + 1

    for row_index, row in enumerate(rows):
        y = origin_y + row_height + 1 + row_index * (row_height + 1)
        if row_index % 2 == 1:
            _fill_rect(pixels, width, origin_x, y, table_width - 1, row_height, _COLOR_ROW_ALT)

        x = origin_x
        for column_index, (key, _, _) in enumerate(_TABLE_COLUMNS):
            text = row[key]
            _draw_text(pixels, width, x + _CELL_PADDING_X, y + _CELL_PADDING_Y, text, _COLOR_TEXT)
            x += col_widths[column_index] + 1

    _draw_grid(pixels, width, origin_x, origin_y, col_widths, row_height, len(rows))
    png_bytes = _encode_png(width=width, height=height, rgb_data=bytes(pixels))
    destination.write_bytes(png_bytes)


def _to_renderable_rows(exposures_df: object) -> list[dict[str, str]]:
    columns = _read_columns(exposures_df)
    missing_columns = sorted(_REQUIRED_COLUMNS - set(columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"exposures_df is missing required columns: {missing}")

    records = _read_records(exposures_df)
    if not records:
        raise ValueError("exposures_df contains no records")

    rendered: list[dict[str, str]] = []
    for index, record in enumerate(records):
        normalized: dict[str, str] = {}
        for key, _, _ in _TABLE_COLUMNS:
            value = record.get(key)
            if key == "Counterparty":
                if value is None or str(value).strip() == "":
                    raise ValueError(f"row {index} is missing a Counterparty value")
                normalized[key] = str(value).strip()
                continue

            number = _coerce_number(value, row_index=index, column_name=key)
            normalized[key] = f"{number:,.2f}"
        rendered.append(normalized)

    return rendered


def _read_columns(exposures_df: object) -> list[str]:
    columns = getattr(exposures_df, "columns", None)
    if columns is None:
        raise ValueError("exposures_df must provide a columns attribute")
    return [str(column) for column in columns]


def _read_records(exposures_df: object) -> list[dict[str, object]]:
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
            value
            if isinstance(value, (str, bytes, bytearray, int, float))
            else cast(Any, value)
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
) -> None:
    table_height = (row_count + 1) * row_height + row_count + 1
    table_width = sum(col_widths) + len(col_widths)

    # Outer border.
    _fill_rect(pixels, image_width, origin_x, origin_y, table_width, 1, _COLOR_GRID)
    _fill_rect(
        pixels,
        image_width,
        origin_x,
        origin_y + table_height,
        table_width,
        1,
        _COLOR_GRID,
    )
    _fill_rect(pixels, image_width, origin_x, origin_y, 1, table_height + 1, _COLOR_GRID)
    _fill_rect(
        pixels,
        image_width,
        origin_x + table_width,
        origin_y,
        1,
        table_height + 1,
        _COLOR_GRID,
    )

    # Inner row boundaries.
    for row in range(1, row_count + 1):
        y = origin_y + row * row_height + (row - 1)
        _fill_rect(pixels, image_width, origin_x, y, table_width + 1, 1, _COLOR_GRID)

    # Inner column boundaries.
    x = origin_x
    for col_width in col_widths[:-1]:
        x += col_width + 1
        _fill_rect(pixels, image_width, x, origin_y, 1, table_height + 1, _COLOR_GRID)


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
