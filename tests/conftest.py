"""Global pytest collection hooks for CI-friendly test selection."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def registered_alias_workbook(tmp_path: Path) -> Path:
    """Real CPRS-FCM input whose two labels represent one registered entity."""
    from openpyxl import Workbook

    path = tmp_path / "registered-aliases.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "CPRS - FCM"
    for row, column, value in (
        (4, 4, "Position"),
        (5, 4, "Counterparty/ FCM"),
        (5, 7, "Nominal"),
        (5, 12, "12/31 Total"),
        (5, 13, "Notional change"),
        (6, 6, "TIPS"),
        (6, 7, "Treasury"),
        (6, 8, "Equity"),
        (6, 9, "Commodity"),
        (6, 10, "Currency"),
        (6, 12, "Notional"),
        (6, 13, "from prior month"),
        (10, 4, "Total by Counterparty/ FCM (This is not the legal obligation exposure)"),
        (23, 4, "FUTURES DETAIL"),
    ):
        sheet.cell(row, column, value)
    for row, name, notional in ((12, "Citibank", 60.0), (13, "Citigroup", -40.0)):
        sheet.cell(row, 4, name)
        sheet.cell(row, 8, notional)
        sheet.cell(row, 12, notional)
    workbook.save(path)
    workbook.close()
    return path


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark integration directory tests as slow for PR-gate runs."""
    slow = pytest.mark.slow
    for item in items:
        item_path = getattr(item, "path", None)
        if item_path is None:
            continue
        try:
            relative_parts = Path(item_path).parts
        except TypeError:
            continue
        if "integration" in relative_parts and "tests" in relative_parts:
            item.add_marker(slow)


@pytest.fixture
def cprs_workflow_config(tmp_path: Path):
    """Real reporting inputs copied away from the immutable fixture archive."""
    import shutil
    from datetime import date

    from counter_risk.config import WorkflowConfig

    fixtures = Path(__file__).parent / "fixtures"
    names = {
        "mosers_all_programs_xlsx": "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
        "mosers_ex_trend_xlsx": "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
        "mosers_trend_xlsx": "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
        "hist_all_programs_3yr_xlsx": "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
        "hist_ex_llc_3yr_xlsx": "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
        "hist_llc_3yr_xlsx": "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
        "monthly_pptx": "Monthly Counterparty Exposure Report.pptx",
    }
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    for name in names.values():
        shutil.copyfile(fixtures / name, inputs / name)
    cash = tmp_path / "repo-cash.csv"
    cash.write_text("counterparty,cash_value\nCIBC,1234567\n")
    return WorkflowConfig(
        **{field: inputs / name for field, name in names.items()},
        as_of_date=date(2025, 12, 31),
        cash_source_type="csv",
        cash_source_path=cash,
        enable_screenshot_replacement=True,
        output_root=tmp_path / "runs",
    )
