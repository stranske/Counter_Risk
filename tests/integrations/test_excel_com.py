"""Behavioral contracts for Excel COM screenshot automation."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from counter_risk.integrations import excel_com


class _FakePageSetup:
    def __init__(self) -> None:
        self.PrintArea = "$Z$99"
        self.Orientation: int | None = None
        self.Zoom: bool | None = None
        self.FitToPagesWide: int | None = None
        self.FitToPagesTall: int | None = None
        self.LeftMargin: float | None = None
        self.RightMargin: float | None = None
        self.TopMargin: float | None = None
        self.BottomMargin: float | None = None
        self.HeaderMargin: float | None = None
        self.FooterMargin: float | None = None
        self.PrintHeadings: bool | None = None
        self.PrintGridlines: bool | None = None


class _FakeRange:
    def __init__(self, address: str) -> None:
        self.Address = address


class _FakeWorksheet:
    def __init__(self) -> None:
        self.PageSetup = _FakePageSetup()
        self.range_calls: list[str] = []
        self.export_calls: list[tuple[int, str]] = []
        self.print_area_during_export: str | None = None

    def Range(self, cell_range: str) -> _FakeRange:  # noqa: N802
        self.range_calls.append(cell_range)
        return _FakeRange(f"${cell_range.replace(':', ':$')}")

    def ExportAsFixedFormat(self, export_type: int, pdf_path: str) -> None:  # noqa: N802
        self.export_calls.append((export_type, pdf_path))
        self.print_area_during_export = self.PageSetup.PrintArea
        Path(pdf_path).write_bytes(b"%PDF-fake")


class _FakeWorksheets:
    def __init__(self, worksheet: _FakeWorksheet) -> None:
        self.worksheet = worksheet
        self.requested_names: list[str] = []

    def __call__(self, sheet_name: str) -> _FakeWorksheet:
        self.requested_names.append(sheet_name)
        return self.worksheet


class _FakeWorkbook:
    def __init__(self, worksheet: _FakeWorksheet) -> None:
        self.Worksheets = _FakeWorksheets(worksheet)
        self.close_args: list[bool] = []

    def Close(self, save_changes: bool) -> None:  # noqa: N802
        self.close_args.append(save_changes)


class _FakeWorkbooks:
    def __init__(self, workbook: _FakeWorkbook) -> None:
        self.workbook = workbook
        self.open_args: list[tuple[str, int, bool]] = []

    def Open(self, path: str, update_links: int, read_only: bool) -> _FakeWorkbook:  # noqa: N802
        self.open_args.append((path, update_links, read_only))
        return self.workbook


class _FakeExcelApp:
    def __init__(self, workbook: _FakeWorkbook) -> None:
        self.Workbooks = _FakeWorkbooks(workbook)
        self.Visible: bool | None = None
        self.DisplayAlerts: bool | None = None
        self.quit_calls = 0

    def Quit(self) -> None:  # noqa: N802
        self.quit_calls += 1


def _fake_excel_graph() -> tuple[_FakeExcelApp, _FakeWorkbook, _FakeWorksheet]:
    worksheet = _FakeWorksheet()
    workbook = _FakeWorkbook(worksheet)
    return _FakeExcelApp(workbook), workbook, worksheet


@pytest.mark.parametrize("field_name", ["workbook_path", "output_png"])
@pytest.mark.parametrize("blank", ["", "  \t"])
def test_export_rejects_blank_paths_before_starting_excel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field_name: str,
    blank: str,
) -> None:
    """Blank config must not become cwd and reach a stateful Excel COM call."""

    workbook_path: str | Path = tmp_path / "input.xlsx"
    Path(workbook_path).write_bytes(b"workbook")
    output_png: str | Path = tmp_path / "output.png"
    if field_name == "workbook_path":
        workbook_path = blank
    else:
        output_png = blank

    monkeypatch.setattr(
        excel_com,
        "initialize_excel_application",
        lambda: pytest.fail("Excel must not start for an invalid path"),
    )

    with pytest.raises(ValueError, match=rf"^{field_name} must not be empty\.$"):
        excel_com.export_worksheet_range_as_png(
            workbook_path=workbook_path,
            sheet_name="CPRS - CH",
            output_png=output_png,
        )


def test_initialize_excel_application_wraps_dispatch_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Callers need a stable integration error without losing the COM root cause."""

    def fail_dispatch(_: str) -> Any:
        raise RuntimeError("class not registered")

    monkeypatch.setattr(excel_com, "_load_dispatch_ex", lambda: fail_dispatch)

    with pytest.raises(excel_com.ExcelComInitializationError) as exc_info:
        excel_com.initialize_excel_application()

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "DispatchEx('Excel.Application')" in str(exc_info.value)


def test_is_excel_com_available_quits_successful_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """An availability probe must not leave a hidden Excel process behind."""

    app, _, _ = _fake_excel_graph()
    monkeypatch.setattr(excel_com, "initialize_excel_application", lambda: app)

    assert excel_com.is_excel_com_available() is True
    assert app.quit_calls == 1


def test_export_opens_read_only_without_link_updates_and_restores_print_area(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Screenshots must not refresh links, mutate, or save the source workbook."""

    source = tmp_path / "input.xlsx"
    source.write_bytes(b"workbook")
    destination = tmp_path / "nested" / "output.png"
    app, workbook, worksheet = _fake_excel_graph()
    monkeypatch.setattr(excel_com, "initialize_excel_application", lambda: app)

    def fake_rasterize(*, pdf_path: Path, output_png: Path) -> None:
        assert pdf_path.read_bytes() == b"%PDF-fake"
        output_png.write_bytes(b"png")

    monkeypatch.setattr(excel_com, "_rasterize_pdf_page_to_png", fake_rasterize)

    returned = excel_com.export_worksheet_range_as_png(
        workbook_path=source,
        sheet_name="CPRS - FCM",
        output_png=destination,
        cell_range="A1:C9",
    )

    assert returned == destination
    assert destination.read_bytes() == b"png"
    assert app.Workbooks.open_args == [(str(source), 0, True)]
    assert workbook.Worksheets.requested_names == ["CPRS - FCM"]
    assert worksheet.range_calls == ["A1:C9"]
    assert worksheet.print_area_during_export == "$A1:$C9"
    assert worksheet.PageSetup.PrintArea == "$Z$99"
    assert worksheet.PageSetup.Orientation == excel_com._XL_LANDSCAPE
    assert worksheet.PageSetup.FitToPagesWide == 1
    assert worksheet.PageSetup.FitToPagesTall == 1
    assert worksheet.PageSetup.PrintGridlines is False
    assert workbook.close_args == [False]
    assert app.quit_calls == 1


def test_export_failure_restores_workbook_state_and_releases_excel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A rasterizer failure must not leak Excel or leave a changed print area."""

    source = tmp_path / "input.xlsx"
    source.write_bytes(b"workbook")
    app, workbook, worksheet = _fake_excel_graph()
    monkeypatch.setattr(excel_com, "initialize_excel_application", lambda: app)

    def fail_rasterize(*, pdf_path: Path, output_png: Path) -> None:
        del pdf_path, output_png
        raise RuntimeError("render failed")

    monkeypatch.setattr(excel_com, "_rasterize_pdf_page_to_png", fail_rasterize)

    with pytest.raises(RuntimeError, match="render failed"):
        excel_com.export_worksheet_range_as_png(
            workbook_path=source,
            sheet_name="CPRS - CH",
            output_png=tmp_path / "output.png",
            cell_range="B2:D8",
        )

    assert worksheet.PageSetup.PrintArea == "$Z$99"
    assert workbook.close_args == [False]
    assert app.quit_calls == 1


def test_missing_worksheet_is_contextual_and_releases_excel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A bad sheet mapping should identify the workbook and still close COM state."""

    source = tmp_path / "input.xlsx"
    source.write_bytes(b"workbook")
    app, workbook, _ = _fake_excel_graph()

    def missing_sheet(_: str) -> Any:
        raise KeyError("missing")

    workbook.Worksheets = missing_sheet
    monkeypatch.setattr(excel_com, "initialize_excel_application", lambda: app)

    with pytest.raises(excel_com.ExcelComError) as exc_info:
        excel_com.export_worksheet_range_as_png(
            workbook_path=source,
            sheet_name="CPRS - FCM",
            output_png=tmp_path / "output.png",
        )

    assert f"Worksheet 'CPRS - FCM' not found in workbook: {source}" == str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert workbook.close_args == [False]
    assert app.quit_calls == 1


def test_resolve_content_range_ignores_formatted_rows_beyond_real_values() -> None:
    """Stray formatting must not shrink a real table into a million-row print area."""

    used_range = types.SimpleNamespace(Row=2, Column=3)
    last_row = types.SimpleNamespace(Row=11)
    last_column = types.SimpleNamespace(Column=8)

    class FakeCells:
        def __init__(self) -> None:
            self.find_calls: list[tuple[Any, ...]] = []

        def __call__(self, row: int, column: int) -> tuple[int, int]:
            return row, column

        def Find(self, *args: Any) -> Any:  # noqa: N802
            self.find_calls.append(args)
            return last_row if args[4] == excel_com._XL_BY_ROWS else last_column

    class FakeWorksheet:
        def __init__(self) -> None:
            self.UsedRange = used_range
            self.Cells = FakeCells()
            self.range_args: tuple[Any, Any] | None = None
            self.bounded_range = object()

        def Range(self, first: Any, last: Any) -> object:  # noqa: N802
            self.range_args = first, last
            return self.bounded_range

    worksheet = FakeWorksheet()

    resolved = excel_com._resolve_content_range(worksheet)

    assert resolved is worksheet.bounded_range
    assert worksheet.range_args == ((2, 3), (11, 8))
    assert [call[4] for call in worksheet.Cells.find_calls] == [
        excel_com._XL_BY_ROWS,
        excel_com._XL_BY_COLUMNS,
    ]


def test_resolve_content_range_keeps_used_range_for_empty_sheet() -> None:
    """An empty sheet has no value-bounded rectangle, so its COM range stays valid."""

    used_range = object()

    class EmptyCells:
        def __call__(self, row: int, column: int) -> tuple[int, int]:
            return row, column

        def Find(self, *args: Any) -> None:  # noqa: N802
            del args
            return None

    worksheet = types.SimpleNamespace(UsedRange=used_range, Cells=EmptyCells())

    assert excel_com._resolve_content_range(worksheet) is used_range


def test_autocrop_removes_white_border_without_discarding_edge_padding() -> None:
    """The exported table must stay legible and retain bounded breathing room."""

    image = Image.new("RGB", (12, 10), "white")
    image.paste("black", (1, 2, 5, 6))

    cropped = excel_com._autocrop_to_content(image, padding=3)

    assert cropped.size == (8, 9)
    assert cropped.getpixel((1, 2)) == (0, 0, 0)


def test_autocrop_keeps_uniform_page_instead_of_producing_empty_image() -> None:
    """A blank exported page should remain inspectable rather than crop to nothing."""

    image = Image.new("RGB", (12, 10), "white")

    assert excel_com._autocrop_to_content(image) is image


def test_rasterizer_closes_pdf_resources_when_png_save_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A disk/write failure must not retain native PDF page or document handles."""

    events: list[str] = []

    class FakeImage:
        def save(self, path: str, image_format: str) -> None:
            events.append(f"save:{Path(path).name}:{image_format}")
            raise OSError("disk full")

    class FakeBitmap:
        def to_pil(self) -> FakeImage:
            events.append("to_pil")
            return FakeImage()

    class FakePage:
        def render(self, *, scale: float) -> FakeBitmap:
            events.append(f"render:{scale}")
            return FakeBitmap()

        def close(self) -> None:
            events.append("page.close")

    class FakePdf:
        def __getitem__(self, index: int) -> FakePage:
            assert index == 0
            events.append("page.open")
            return FakePage()

        def close(self) -> None:
            events.append("pdf.close")

    fake_pdfium = types.ModuleType("pypdfium2")
    fake_pdfium.PdfDocument = lambda _: FakePdf()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pypdfium2", fake_pdfium)
    monkeypatch.setattr(excel_com, "_autocrop_to_content", lambda image: image)

    with pytest.raises(OSError, match="disk full"):
        excel_com._rasterize_pdf_page_to_png(
            pdf_path=tmp_path / "input.pdf",
            output_png=tmp_path / "output.png",
        )

    assert events == [
        "page.open",
        f"render:{excel_com._RENDER_SCALE}",
        "to_pil",
        "page.close",
        "save:output.png:PNG",
        "pdf.close",
    ]
