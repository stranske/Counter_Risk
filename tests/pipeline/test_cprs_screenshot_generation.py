"""Tests for CPRS-CH/CPRS-FCM screenshot generation orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import counter_risk.pipeline.run as run_module
from counter_risk.config import WorkflowConfig
from counter_risk.integrations import excel_com


def _build_config(tmp_path: Path, **overrides: Any) -> WorkflowConfig:
    placeholder_files = (
        "all.xlsx",
        "ex.xlsx",
        "trend.xlsx",
        "hist_all.xlsx",
        "hist_ex.xlsx",
        "hist_llc.xlsx",
        "monthly.pptx",
    )
    for filename in placeholder_files:
        (tmp_path / filename).write_bytes(b"placeholder")

    defaults: dict[str, Any] = {
        "mosers_all_programs_xlsx": tmp_path / "all.xlsx",
        "mosers_ex_trend_xlsx": tmp_path / "ex.xlsx",
        "mosers_trend_xlsx": tmp_path / "trend.xlsx",
        "hist_all_programs_3yr_xlsx": tmp_path / "hist_all.xlsx",
        "hist_ex_llc_3yr_xlsx": tmp_path / "hist_ex.xlsx",
        "hist_llc_3yr_xlsx": tmp_path / "hist_llc.xlsx",
        "monthly_pptx": tmp_path / "monthly.pptx",
    }
    defaults.update(overrides)
    return WorkflowConfig(**defaults)


@pytest.mark.parametrize("cash_override", [None, 7654321, 0, -1234567])
def test_generates_screenshot_for_each_configured_variant_and_table_adjusted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cprs_workflow_config: WorkflowConfig,
    cash_override: int | None,
) -> None:
    import hashlib

    config = cprs_workflow_config
    expected_cash = 1234567 if cash_override is None else cash_override
    if cash_override is not None:
        overrides = tmp_path / "cash-overrides.csv"
        overrides.write_text(f"counterparty,cash_value\nCIBC,{cash_override}\n")
        config = config.model_copy(update={"cash_overrides_csv": overrides})
    original_hashes = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (tmp_path / "inputs").iterdir()
    }
    run_dir = tmp_path / "run"
    warnings: list[str] = []
    calls: list[dict[str, Any]] = []
    parsed = run_module._parse_inputs(run_module._resolve_input_paths(config))
    run_module._apply_daily_holdings_repo_cash(
        config=config, parsed_by_variant=parsed, warnings=warnings, as_of_date=config.as_of_date
    )
    paths = run_module._write_cprs_reporting_workbooks(
        config=config, parsed_by_variant=parsed, run_dir=run_dir, repo_cash_applied=True
    )
    warnings.clear()

    def _fake_export(*, workbook_path: Path, sheet_name: str, output_png: Path) -> Path:
        from openpyxl import load_workbook

        if workbook_path in {paths["all_programs"], config.mosers_all_programs_xlsx}:
            workbook = load_workbook(workbook_path, data_only=True)
            try:
                rows = list(workbook[sheet_name].values)
                cash = [row[3] for row in rows if len(row) > 3 and row[2] == "CIBC"]
                assert cash == [expected_cash], "exporter must read adjusted CIBC cash"
            finally:
                workbook.close()
        assert workbook_path.is_relative_to(run_dir)
        calls.append(
            {"workbook_path": workbook_path, "sheet_name": sheet_name, "output_png": output_png}
        )
        output_png.parent.mkdir(parents=True, exist_ok=True)
        from PIL import Image

        Image.new("RGB", (20, 20), "blue").save(output_png)
        return output_png

    monkeypatch.setattr(excel_com, "export_worksheet_range_as_png", _fake_export)

    result = run_module._generate_cprs_screenshot_inputs(
        workbook_paths=paths, config=config, run_dir=run_dir, warnings=warnings
    )

    assert set(result) == {"slide1", "slide2", "slide6", "slide7", "slide16", "slide17"}
    assert warnings == []
    assert len(calls) == 6

    call_by_sheet_and_workbook = {(call["sheet_name"], call["workbook_path"]) for call in calls}
    assert (("CPRS - CH", paths["all_programs"])) in call_by_sheet_and_workbook
    assert (("CPRS - FCM", paths["all_programs"])) in call_by_sheet_and_workbook
    assert (("CPRS - CH", paths["ex_trend"])) in call_by_sheet_and_workbook
    assert (("CPRS - FCM", paths["ex_trend"])) in call_by_sheet_and_workbook
    assert (("CPRS - CH", paths["trend"])) in call_by_sheet_and_workbook
    assert (("CPRS - FCM", paths["trend"])) in call_by_sheet_and_workbook

    for path in result.values():
        assert path.is_relative_to(run_dir)
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    for variant in ("ex_trend", "trend"):
        source = getattr(config, run_module._CPRS_SCREENSHOT_WORKBOOK_FIELD_BY_VARIANT[variant])
        assert paths[variant].read_bytes() == source.read_bytes()
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in original_hashes
    } == original_hashes


def test_skips_variant_without_configured_workbook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, mosers_trend_xlsx=None)
    run_dir = tmp_path / "run"
    warnings: list[str] = []

    def _fake_export(*, workbook_path: Path, sheet_name: str, output_png: Path) -> Path:
        output_png.parent.mkdir(parents=True, exist_ok=True)
        output_png.write_bytes(b"fake-png")
        return output_png

    monkeypatch.setattr(excel_com, "export_worksheet_range_as_png", _fake_export)

    result = run_module._generate_cprs_screenshot_inputs(
        workbook_paths={
            variant: path
            for variant, field in run_module._CPRS_SCREENSHOT_WORKBOOK_FIELD_BY_VARIANT.items()
            if (path := getattr(config, field)) is not None
        },
        config=config,
        run_dir=run_dir,
        warnings=warnings,
    )

    assert set(result) == {"slide1", "slide2", "slide6", "slide7"}
    assert "slide16" not in result
    assert "slide17" not in result
    assert warnings == []


def test_export_failure_appends_warning_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path)
    run_dir = tmp_path / "run"
    warnings: list[str] = []

    def _fake_export(*, workbook_path: Path, sheet_name: str, output_png: Path) -> Path:
        if sheet_name == "CPRS - FCM" and workbook_path == config.mosers_all_programs_xlsx:
            raise excel_com.ExcelComError("boom")
        output_png.parent.mkdir(parents=True, exist_ok=True)
        output_png.write_bytes(b"fake-png")
        return output_png

    monkeypatch.setattr(excel_com, "export_worksheet_range_as_png", _fake_export)

    result = run_module._generate_cprs_screenshot_inputs(
        workbook_paths={
            variant: path
            for variant, field in run_module._CPRS_SCREENSHOT_WORKBOOK_FIELD_BY_VARIANT.items()
            if (path := getattr(config, field)) is not None
        },
        config=config,
        run_dir=run_dir,
        warnings=warnings,
    )

    assert "slide2" not in result
    assert set(result) == {"slide1", "slide6", "slide7", "slide16", "slide17"}
    assert len(warnings) == 1
    assert "all_programs/fcm" in warnings[0]
    assert "slide 2" in warnings[0]


def test_pad_image_to_aspect_ratio_widens_canvas_without_cropping(tmp_path: Path) -> None:
    from PIL import Image

    image_path = tmp_path / "table.png"
    Image.new("RGB", (200, 200), (10, 20, 30)).save(image_path, "PNG")

    run_module._pad_image_to_aspect_ratio(image_path, target_ratio=2.0)

    with Image.open(image_path) as padded:
        assert padded.size == (400, 200)
        # Original content is preserved, centered, not cropped or squished.
        assert padded.getpixel((50, 100)) == (255, 255, 255)
        assert padded.getpixel((200, 100)) == (10, 20, 30)


def test_pad_image_to_aspect_ratio_heightens_canvas_without_cropping(tmp_path: Path) -> None:
    from PIL import Image

    image_path = tmp_path / "table.png"
    Image.new("RGB", (200, 200), (10, 20, 30)).save(image_path, "PNG")

    run_module._pad_image_to_aspect_ratio(image_path, target_ratio=0.5)

    with Image.open(image_path) as padded:
        assert padded.size == (200, 400)
        assert padded.getpixel((100, 50)) == (255, 255, 255)
        assert padded.getpixel((100, 200)) == (10, 20, 30)


def test_pad_image_to_aspect_ratio_noop_when_already_matching(tmp_path: Path) -> None:
    from PIL import Image

    image_path = tmp_path / "table.png"
    Image.new("RGB", (300, 200), (10, 20, 30)).save(image_path, "PNG")
    original_bytes = image_path.read_bytes()

    run_module._pad_image_to_aspect_ratio(image_path, target_ratio=1.5)

    assert image_path.read_bytes() == original_bytes


def test_picture_shape_aspect_ratio_returns_none_for_unreadable_pptx(tmp_path: Path) -> None:
    bad_pptx = tmp_path / "not_a_pptx.pptx"
    bad_pptx.write_bytes(b"not a real pptx")

    assert run_module._picture_shape_aspect_ratio(pptx_path=bad_pptx, slide_number=1) is None


def test_picture_shape_aspect_ratio_reads_real_template(tmp_path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Emu

    pptx_path = tmp_path / "template.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    placeholder_png = tmp_path / "placeholder.png"
    from PIL import Image

    Image.new("RGB", (10, 10), (255, 255, 255)).save(placeholder_png, "PNG")
    slide.shapes.add_picture(
        str(placeholder_png), Emu(0), Emu(0), width=Emu(914400 * 4), height=Emu(914400 * 2)
    )
    presentation.save(str(pptx_path))

    ratio = run_module._picture_shape_aspect_ratio(pptx_path=pptx_path, slide_number=1)

    assert ratio == pytest.approx(2.0)


def test_reporting_workbooks_without_adjustment_are_byte_identical(
    tmp_path: Path,
    cprs_workflow_config: WorkflowConfig,
) -> None:
    config = cprs_workflow_config
    paths = run_module._write_cprs_reporting_workbooks(
        config=config, parsed_by_variant={}, run_dir=tmp_path / "run", repo_cash_applied=False
    )
    for variant, path in paths.items():
        source = getattr(config, run_module._CPRS_SCREENSHOT_WORKBOOK_FIELD_BY_VARIANT[variant])
        assert path != source
        assert path.read_bytes() == source.read_bytes()


def test_adjusted_reporting_handles_new_rows_and_collapsed_duplicates(
    tmp_path: Path,
    cprs_workflow_config: WorkflowConfig,
) -> None:
    import hashlib

    from openpyxl import load_workbook

    from counter_risk.parsers import parse_cprs_ch, parse_fcm_totals

    config = cprs_workflow_config
    source = config.mosers_all_programs_xlsx
    assert source is not None and config.cash_source_path is not None
    workbook = load_workbook(source)
    worksheet = workbook["CPRS - CH"]
    worksheet["D6"] = "Cash"
    worksheet["C22"] = "Morgan Stanley"
    worksheet["D22"] = 999
    workbook.save(source)
    workbook.close()
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    cash = {"Morgan Stanley": 100, "CIBC": 200, "ASL": 300, "Scotia": 400, "Daiwa": 500}
    config.cash_source_path.write_text(
        "counterparty,cash_value\n" + "".join(f"{name},{amount}\n" for name, amount in cash.items())
    )
    parsed = run_module._parse_inputs(run_module._resolve_input_paths(config))
    run_module._apply_daily_holdings_repo_cash(
        config=config, parsed_by_variant=parsed, warnings=[], as_of_date=config.as_of_date
    )
    paths = run_module._write_cprs_reporting_workbooks(
        config=config, parsed_by_variant=parsed, run_dir=tmp_path / "run", repo_cash_applied=True
    )
    repo = [
        row
        for row in run_module._records(parse_cprs_ch(paths["all_programs"]))
        if row["Segment"] == "repo"
    ]
    for name, amount in cash.items():
        assert [row["Cash"] for row in repo if row["Counterparty"] == name] == [amount]
    # New FCM totals are also inside the totals section, ahead of futures detail.
    totals = run_module._records(parse_fcm_totals(paths["all_programs"]))
    assert next(row["Notional"] for row in totals if row["counterparty"] == "CIBC") == 200
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash


def test_adjusted_reporting_snapshot_reports_missing_repo_segment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cprs_workflow_config: WorkflowConfig
) -> None:
    from hashlib import sha256

    from counter_risk.parsers import cprs_ch

    source = cprs_workflow_config.mosers_all_programs_xlsx
    original_hash = sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(cprs_ch, "_scan_segments", lambda _rows: [])
    with pytest.raises(ValueError, match="missing the Repo segment"):
        run_module._write_cprs_reporting_workbooks(
            config=cprs_workflow_config,
            parsed_by_variant={"all_programs": {}},
            run_dir=tmp_path / "run",
            repo_cash_applied=True,
        )
    assert sha256(source.read_bytes()).hexdigest() == original_hash


def test_adjusted_reporting_keeps_cash_column_when_tips_header_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cprs_workflow_config: WorkflowConfig
) -> None:
    """Cash-present / TIPS-absent CH maps must not KeyError on the Cash fallback."""
    from hashlib import sha256

    from counter_risk.parsers import cprs_ch, parse_cprs_ch

    config = cprs_workflow_config
    source = config.mosers_all_programs_xlsx
    assert source is not None
    original_hash = sha256(source.read_bytes()).hexdigest()
    parsed = run_module._parse_inputs(run_module._resolve_input_paths(config))
    run_module._apply_daily_holdings_repo_cash(
        config=config, parsed_by_variant=parsed, warnings=[], as_of_date=config.as_of_date
    )
    original_build = cprs_ch._build_column_map

    def _cash_without_tips(rows: Any, header: int) -> dict[str, int]:
        columns = original_build(rows, header)
        columns.pop("TIPS", None)
        columns.setdefault("Cash", 4)
        return columns

    monkeypatch.setattr(cprs_ch, "_build_column_map", _cash_without_tips)
    paths = run_module._write_cprs_reporting_workbooks(
        config=config, parsed_by_variant=parsed, run_dir=tmp_path / "run", repo_cash_applied=True
    )
    monkeypatch.setattr(cprs_ch, "_build_column_map", original_build)
    repo = [
        row
        for row in run_module._records(parse_cprs_ch(paths["all_programs"]))
        if row["Segment"] == "repo"
    ]
    assert any(row["Counterparty"] == "CIBC" for row in repo)
    assert sha256(source.read_bytes()).hexdigest() == original_hash


def test_adjusted_reporting_reports_missing_ch_cash_and_tips_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cprs_workflow_config: WorkflowConfig
) -> None:
    from hashlib import sha256

    from counter_risk.parsers import cprs_ch

    source = cprs_workflow_config.mosers_all_programs_xlsx
    original_hash = sha256(source.read_bytes()).hexdigest()
    original_build = cprs_ch._build_column_map

    def _neither_cash_nor_tips(rows: Any, header: int) -> dict[str, int]:
        columns = original_build(rows, header)
        columns.pop("Cash", None)
        columns.pop("TIPS", None)
        return columns

    monkeypatch.setattr(cprs_ch, "_build_column_map", _neither_cash_nor_tips)
    with pytest.raises(ValueError, match="missing the CH Cash/TIPS columns"):
        run_module._write_cprs_reporting_workbooks(
            config=cprs_workflow_config,
            parsed_by_variant={"all_programs": {}},
            run_dir=tmp_path / "run",
            repo_cash_applied=True,
        )
    assert sha256(source.read_bytes()).hexdigest() == original_hash


def test_adjusted_reporting_preserves_uncached_formulas_and_freezes_cached_results(
    tmp_path: Path, cprs_workflow_config: WorkflowConfig
) -> None:
    from hashlib import sha256
    from zipfile import ZIP_DEFLATED, ZipFile

    from openpyxl import load_workbook

    config = cprs_workflow_config
    source = config.mosers_all_programs_xlsx
    assert source is not None
    workbook = load_workbook(source)
    # Outside the Repo and FCM sections, including an unrelated worksheet.
    for name in ("CPRS - CH", "CPRS - FCM"):
        workbook[name]["J1"] = "=1+1"
    audit = workbook.create_sheet("Formula audit")
    audit.append(["=2-2", "=1+2", '=IF(TRUE,"ready","")', "=4+4", "literal"])
    workbook.save(source)
    workbook.close()
    # Model Excel caches, including zero and a string; D1 stays uncached.
    with ZipFile(source) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    sheet_path = next(
        name
        for name, data in entries.items()
        if name.startswith("xl/worksheets/") and b"Formula audit" not in data and b"2-2</f>" in data
    )
    xml = entries[sheet_path]
    xml = xml.replace(b"<f>2-2</f><v></v>", b"<f>2-2</f><v>0</v>")
    xml = xml.replace(b"<f>1+2</f><v></v>", b"<f>1+2</f><v>3</v>")
    xml = xml.replace(b'r="C1"', b'r="C1" t="str"')
    xml = xml.replace(b'<v></v></c><c r="D1"', b'<v>=ready</v></c><c r="D1"')
    entries[sheet_path] = xml
    with ZipFile(source, "w", ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    original_hash = sha256(source.read_bytes()).hexdigest()
    parsed = run_module._parse_inputs(run_module._resolve_input_paths(config))
    run_module._apply_daily_holdings_repo_cash(
        config=config, parsed_by_variant=parsed, warnings=[], as_of_date=config.as_of_date
    )
    paths = run_module._write_cprs_reporting_workbooks(
        config=config, parsed_by_variant=parsed, run_dir=tmp_path / "run", repo_cash_applied=True
    )
    snapshot = load_workbook(paths["all_programs"], data_only=False)
    try:
        for name in ("CPRS - CH", "CPRS - FCM"):
            assert snapshot[name]["J1"].value == "=1+1"
        assert [cell.value for cell in snapshot["Formula audit"][1]] == [
            0,
            3,
            "=ready",
            "=4+4",
            "literal",
        ]
        assert snapshot["Formula audit"]["C1"].data_type == "s"
    finally:
        snapshot.close()
    assert sha256(source.read_bytes()).hexdigest() == original_hash
