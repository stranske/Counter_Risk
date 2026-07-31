"""Windows COM helpers for Excel worksheet-range screenshot automation."""

from __future__ import annotations

import importlib.util
import logging
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

_XL_TYPE_PDF = 0
_XL_LANDSCAPE = 2
_PRINT_MARGIN_POINTS = 8.0
_RENDER_SCALE = 3.0  # ~216 DPI; keeps small numeric columns legible.
_AUTOCROP_PADDING_PX = 10
# Excel Find() constants used to bound the real content of a sheet.
_XL_VALUES = -4163
_XL_PART = 2
_XL_BY_ROWS = 1
_XL_BY_COLUMNS = 2
_XL_PREVIOUS = 2


class ExcelComError(RuntimeError):
    """Base error for Excel COM integration failures."""


class ExcelComUnavailableError(ExcelComError):
    """Raised when Excel COM support is not available."""


class ExcelComInitializationError(ExcelComError):
    """Raised when an Excel COM application instance cannot be started."""


def _as_path(path: str | Path, *, field_name: str) -> Path:
    resolved = Path(path)
    if not str(resolved):
        raise ValueError(f"{field_name} must not be empty.")
    return resolved


def _run_com_cleanup(*, action: str, callback: Any) -> None:
    try:
        callback()
    except Exception as exc:
        LOGGER.error(
            "Excel COM cleanup failed action=%s exc_type=%s exc=%s",
            action,
            type(exc).__name__,
            exc,
        )


def _load_dispatch_ex() -> Any:
    """Load and return the ``DispatchEx`` COM constructor for Excel automation."""

    if sys.platform != "win32":
        raise ExcelComUnavailableError(
            "Excel COM automation is only available on Windows (sys.platform == 'win32')."
        )

    if importlib.util.find_spec("win32com.client") is None:
        raise ExcelComUnavailableError(
            "Missing win32com.client; install pywin32 on a Windows host with Office installed."
        )

    try:
        from win32com.client import DispatchEx  # type: ignore[import-untyped]
    except Exception as exc:
        raise ExcelComUnavailableError(
            "win32com.client is present but failed to import cleanly."
        ) from exc

    return DispatchEx


def initialize_excel_application() -> Any:
    """Initialize and return an Excel COM application object.

    Raises:
        ExcelComUnavailableError: COM prerequisites are missing.
        ExcelComInitializationError: Excel COM failed to launch.
    """

    dispatch_ex = _load_dispatch_ex()

    try:
        app = dispatch_ex("Excel.Application")
    except Exception as exc:
        raise ExcelComInitializationError(
            "Failed to initialize Excel COM via DispatchEx('Excel.Application')."
        ) from exc

    return app


def is_excel_com_available() -> bool:
    """Return ``True`` if Excel COM appears callable on this host."""

    try:
        app = initialize_excel_application()
    except ExcelComError:
        return False

    _run_com_cleanup(action="app.Quit", callback=app.Quit)
    return True


def _autocrop_to_content(image: Any, *, padding: int = _AUTOCROP_PADDING_PX) -> Any:
    """Crop away the uniform white page border left by the PDF page render."""

    from PIL import Image, ImageChops

    rgb_image = image.convert("RGB")
    background = Image.new("RGB", rgb_image.size, (255, 255, 255))
    bbox = ImageChops.difference(rgb_image, background).getbbox()
    if bbox is None:
        return image

    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(rgb_image.width, right + padding)
    bottom = min(rgb_image.height, bottom + padding)
    return image.crop((left, top, right, bottom))


def export_worksheet_range_as_png(
    *,
    workbook_path: str | Path,
    sheet_name: str,
    output_png: str | Path,
    cell_range: str | None = None,
) -> Path:
    """Export a worksheet range as a PNG image via Excel COM.

    Mirrors the manual "snip an image of the tab" step from the Counterparty
    Risk Report Procedures: opens *workbook_path* read-only, prints
    *cell_range* (the sheet's ``UsedRange`` by default) to a temporary
    single-page PDF, rasterizes that page, and crops away the resulting white
    page border. Printing (rather than clipboard copy/paste into a chart
    object) is used because clipboard-based screenshots are unreliable when
    Excel is running headless/invisible under COM automation.

    Raises:
        FileNotFoundError: The workbook file does not exist.
        ExcelComError: COM initialization/open errors.
    """

    source_path = _as_path(workbook_path, field_name="workbook_path")
    if not source_path.exists():
        raise FileNotFoundError(f"Workbook not found: {source_path}")

    destination = _as_path(output_png, field_name="output_png")
    destination.parent.mkdir(parents=True, exist_ok=True)

    app = initialize_excel_application()
    workbook: Any | None = None
    page_setup: Any | None = None
    original_print_area: Any | None = None
    try:
        with suppress(Exception):
            # Some environments' Office security policy blocks hiding the app
            # window (COM error "Application.Visible : Invalid request").
            # Printing to PDF below does not require a visible window.
            app.Visible = False
        with suppress(Exception):
            app.DisplayAlerts = False

        # Filename, UpdateLinks=0 (don't update external links), ReadOnly=True
        workbook = app.Workbooks.Open(str(source_path), 0, True)
        try:
            worksheet = workbook.Worksheets(sheet_name)
        except Exception as exc:
            raise ExcelComError(
                f"Worksheet '{sheet_name}' not found in workbook: {source_path}"
            ) from exc

        target_range = (
            worksheet.Range(cell_range) if cell_range else _resolve_content_range(worksheet)
        )

        page_setup = worksheet.PageSetup
        original_print_area = page_setup.PrintArea
        page_setup.PrintArea = target_range.Address
        page_setup.Orientation = _XL_LANDSCAPE
        page_setup.Zoom = False
        page_setup.FitToPagesWide = 1
        page_setup.FitToPagesTall = 1
        page_setup.LeftMargin = _PRINT_MARGIN_POINTS
        page_setup.RightMargin = _PRINT_MARGIN_POINTS
        page_setup.TopMargin = _PRINT_MARGIN_POINTS
        page_setup.BottomMargin = _PRINT_MARGIN_POINTS
        page_setup.HeaderMargin = 0.0
        page_setup.FooterMargin = 0.0
        page_setup.PrintHeadings = False
        page_setup.PrintGridlines = False

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "range_snapshot.pdf"
            worksheet.ExportAsFixedFormat(_XL_TYPE_PDF, str(pdf_path))
            _rasterize_pdf_page_to_png(pdf_path=pdf_path, output_png=destination)

        LOGGER.info(
            "excel_range_screenshot_complete workbook=%s sheet=%s output=%s",
            source_path,
            sheet_name,
            destination,
        )
    finally:
        if page_setup is not None and original_print_area is not None:
            with suppress(Exception):
                page_setup.PrintArea = original_print_area
        if workbook is not None:
            _run_com_cleanup(action="workbook.Close", callback=lambda: workbook.Close(False))
        _run_com_cleanup(action="app.Quit", callback=app.Quit)

    return destination


def _resolve_content_range(worksheet: Any) -> Any:
    """Return the range covering the sheet's real content.

    ``UsedRange`` is unreliable as a print area: stray whole-column formatting can
    inflate it to the full sheet (observed: the ex-Trend "CPRS - FCM" tab reports
    A1:I1048575 for a 9-row table). Printing that with FitToPagesTall=1 shrinks a
    million rows onto one page, so the actual table renders microscopic and the
    resulting screenshot is an illegible blur. Bound the range with Find() on the
    last row/column that actually holds a value; fall back to ``UsedRange`` if the
    lookup fails or the sheet is empty.
    """
    used_range = worksheet.UsedRange
    try:
        last_row_cell = worksheet.Cells.Find(
            "*", worksheet.Cells(1, 1), _XL_VALUES, _XL_PART, _XL_BY_ROWS, _XL_PREVIOUS
        )
        last_col_cell = worksheet.Cells.Find(
            "*", worksheet.Cells(1, 1), _XL_VALUES, _XL_PART, _XL_BY_COLUMNS, _XL_PREVIOUS
        )
        if last_row_cell is None or last_col_cell is None:
            return used_range
        last_row = int(last_row_cell.Row)
        last_column = int(last_col_cell.Column)
        first_row = int(used_range.Row)
        first_column = int(used_range.Column)
        if last_row < first_row or last_column < first_column:
            return used_range
        return worksheet.Range(
            worksheet.Cells(first_row, first_column),
            worksheet.Cells(last_row, last_column),
        )
    except Exception:  # pragma: no cover - COM/runtime dependent
        return used_range


def _rasterize_pdf_page_to_png(*, pdf_path: Path, output_png: Path) -> None:
    import pypdfium2 as pdfium  # type: ignore[import-untyped]

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[0]
        try:
            bitmap = page.render(scale=_RENDER_SCALE)
            image = bitmap.to_pil()
        finally:
            page.close()
        cropped = _autocrop_to_content(image)
        cropped.save(str(output_png), "PNG")
    finally:
        pdf.close()


__all__ = [
    "ExcelComError",
    "ExcelComUnavailableError",
    "ExcelComInitializationError",
    "initialize_excel_application",
    "is_excel_com_available",
    "export_worksheet_range_as_png",
]
