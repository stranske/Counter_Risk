"""Boundary cases for structured cash ingestion and source dispatch."""

from pathlib import Path

import pytest

from counter_risk.parsers import daily_holdings_pdf
from counter_risk.parsers.repo_cash_sources import (
    find_duplicate_counterparty_names,
    load_cash_by_counterparty,
    load_repo_cash_overrides_csv,
    load_repo_cash_structured_source,
)


@pytest.mark.parametrize("suffix", [".xlsx", ".xlsm"])
def test_inferred_workbook_source_skips_empty_headers_and_rows(tmp_path: Path, suffix: str) -> None:
    workbook = pytest.importorskip("openpyxl").Workbook()
    path = tmp_path / f"cash{suffix}"
    sheet = workbook.active
    sheet.append([" Name ", None, " Repo Cash "])
    sheet.append(["CIBC", "ignored", "1,234.5"])
    sheet.append([None, None, 999])
    sheet.append(["ASL", None, None])
    sheet.append(["CIBC", None, 0])
    workbook.save(path)
    workbook.close()

    assert load_repo_cash_structured_source(path) == {"CIBC": 0.0}
    assert find_duplicate_counterparty_names(path) == ["CIBC"]
    assert load_cash_by_counterparty(source_type=None, source_path=path) == (
        {"CIBC": 0.0},
        [],
        f"xlsx:{path}",
        ["CIBC"],
    )


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_empty_structured_sources_and_overrides(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"empty{suffix}"
    if suffix == ".xlsx":
        workbook = pytest.importorskip("openpyxl").Workbook()
        workbook.save(path)
        workbook.close()
    else:
        path.write_text("counterparty,cash_value\n", encoding="utf-8")
        assert load_repo_cash_overrides_csv(path) == ({}, [])
    assert load_repo_cash_structured_source(path) == {}
    assert find_duplicate_counterparty_names(path) == []


def test_override_blank_fields_are_skipped_and_empty_overrides_preserve_source(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cash.csv"
    path.write_text("counterparty,cash_value\nCIBC,12\n", encoding="utf-8")
    overrides = tmp_path / "overrides.csv"
    overrides.write_text(
        "counterparty,cash_value,note\n,999,no name\nCIBC,,no value\n", encoding="utf-8"
    )
    assert load_repo_cash_overrides_csv(overrides) == ({}, [])
    assert load_cash_by_counterparty(
        source_type="csv", source_path=path, overrides_path=overrides
    ) == ({"CIBC": 12.0}, [], f"csv:{path}", [])


@pytest.mark.parametrize(
    ("source_type", "filename", "message"),
    [
        ("xlsx", "cash.csv", "cash_source_type=xlsx requires a .xlsx/.xlsm file path"),
        (None, "cash.txt", "Unsupported cash source extension"),
    ],
)
def test_structured_source_rejects_unsupported_type_or_extension(
    tmp_path: Path, source_type: str | None, filename: str, message: str
) -> None:
    path = tmp_path / filename
    with pytest.raises(ValueError, match=message):
        load_repo_cash_structured_source(path, source_type=source_type)


def test_cash_dispatch_rejects_unknown_extension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Cannot determine cash source type"):
        load_cash_by_counterparty(source_type=None, source_path=tmp_path / "cash.txt")


def test_pdf_inference_uses_default_parser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cash.PDF"
    calls: list[Path] = []

    def parse(source: Path) -> dict[str, float]:
        calls.append(source)
        return {"CIBC": 7.0}

    monkeypatch.setattr(daily_holdings_pdf, "parse_daily_holdings_pdf", parse)
    assert load_cash_by_counterparty(source_type=None, source_path=path) == (
        {"CIBC": 7.0},
        [],
        f"pdf:{path}",
        [],
    )
    assert calls == [path]


@pytest.mark.parametrize("headers", ["counterparty,other", "other,cash_value"])
def test_missing_cash_schema_is_rejected_but_duplicate_scan_is_safe(
    tmp_path: Path, headers: str
) -> None:
    path = tmp_path / "cash.csv"
    path.write_text(headers + "\nCIBC,2\n", encoding="utf-8")
    assert find_duplicate_counterparty_names(path) == []
    with pytest.raises(ValueError, match="must include counterparty and cash columns"):
        load_repo_cash_structured_source(path)
