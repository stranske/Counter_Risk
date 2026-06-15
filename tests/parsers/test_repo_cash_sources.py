"""Tests for structured Repo Cash source ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.parsers.repo_cash_sources import (
    find_duplicate_counterparty_names,
    load_cash_by_counterparty,
    load_repo_cash_overrides_csv,
    load_repo_cash_structured_source,
)


def test_load_repo_cash_structured_source_from_csv(tmp_path: Path) -> None:
    source_path = tmp_path / "repo_cash.csv"
    source_path.write_text(
        "\n".join(
            [
                "counterparty,cash_value",
                "CIBC,2.0",
                "ASL,3.5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    values = load_repo_cash_structured_source(source_path, source_type="csv")

    assert values["CIBC"] == 2.0
    assert values["ASL"] == 3.5


def test_load_repo_cash_structured_source_from_xlsx(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    source_path = tmp_path / "repo_cash.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "RepoCash"
    sheet.append(["counterparty_name", "cash"])
    sheet.append(["CIBC", "1.25"])
    sheet.append(["ASL", 2.75])
    workbook.save(source_path)

    values = load_repo_cash_structured_source(source_path, source_type="xlsx")

    assert values["CIBC"] == 1.25
    assert values["ASL"] == 2.75


def test_load_repo_cash_overrides_csv_returns_mapping_and_audit_rows(tmp_path: Path) -> None:
    overrides_path = tmp_path / "cash_overrides_2025-12-31.csv"
    overrides_path.write_text(
        "\n".join(
            [
                "counterparty,cash_value,note",
                "CIBC,9.0,manual correction",
                "ASL,4.5,desk override",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    mapping, audit_rows = load_repo_cash_overrides_csv(overrides_path)

    assert mapping["CIBC"] == 9.0
    assert mapping["ASL"] == 4.5
    assert audit_rows[0]["note"] == "manual correction"


def test_load_repo_cash_structured_source_raises_for_source_type_extension_mismatch(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "repo_cash.xlsx"
    source_path.write_text("counterparty,cash_value\nCIBC,1.0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="cash_source_type=csv requires a .csv file path"):
        load_repo_cash_structured_source(source_path, source_type="csv")


# ---------------------------------------------------------------------------
# load_cash_by_counterparty tests
# ---------------------------------------------------------------------------


def test_load_cash_by_counterparty_from_csv(tmp_path: Path) -> None:
    source_path = tmp_path / "repo_cash.csv"
    source_path.write_text(
        "counterparty,cash_value\nCIBC,5.0\nASL,2.5\n",
        encoding="utf-8",
    )

    cash, audit_rows, source_label, duplicates = load_cash_by_counterparty(
        source_type="csv",
        source_path=source_path,
    )

    assert cash["CIBC"] == 5.0
    assert cash["ASL"] == 2.5
    assert audit_rows == []
    assert "csv:" in source_label
    assert duplicates == []


def test_load_cash_by_counterparty_from_xlsx(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    source_path = tmp_path / "repo_cash.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["counterparty", "cash_value"])
    sheet.append(["CIBC", 7.0])
    sheet.append(["ASL", 1.5])
    workbook.save(source_path)

    cash, audit_rows, source_label, duplicates = load_cash_by_counterparty(
        source_type="xlsx",
        source_path=source_path,
    )

    assert cash["CIBC"] == 7.0
    assert cash["ASL"] == 1.5
    assert audit_rows == []
    assert "xlsx:" in source_label
    assert duplicates == []


def test_load_cash_by_counterparty_with_pdf_parser_callable(tmp_path: Path) -> None:
    fake_pdf = tmp_path / "holdings.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fixture")

    def _fake_parser(path: Path) -> dict[str, float]:
        return {"CIBC": 9.0, "Daiwa": 3.0}

    cash, audit_rows, source_label, duplicates = load_cash_by_counterparty(
        source_type="pdf",
        source_path=fake_pdf,
        pdf_parser=_fake_parser,
    )

    assert cash["CIBC"] == 9.0
    assert cash["Daiwa"] == 3.0
    assert audit_rows == []
    assert "pdf:" in source_label
    assert duplicates == []


def test_load_cash_by_counterparty_override_precedence(tmp_path: Path) -> None:
    source_path = tmp_path / "repo_cash.csv"
    source_path.write_text(
        "counterparty,cash_value\nCIBC,5.0\nASL,2.5\n",
        encoding="utf-8",
    )
    overrides_path = tmp_path / "cash_overrides_2025-12-31.csv"
    overrides_path.write_text(
        "counterparty,cash_value,note\nCIBC,99.0,desk correction\n",
        encoding="utf-8",
    )

    cash, audit_rows, source_label, duplicates = load_cash_by_counterparty(
        source_type="csv",
        source_path=source_path,
        overrides_path=overrides_path,
    )

    assert cash["CIBC"] == 99.0, "Override should take precedence over source"
    assert cash["ASL"] == 2.5, "Non-overridden source value should be preserved"
    assert len(audit_rows) == 1
    assert audit_rows[0]["counterparty"] == "CIBC"
    assert audit_rows[0]["note"] == "desk correction"


def test_load_cash_by_counterparty_none_source_returns_empty(tmp_path: Path) -> None:
    cash, audit_rows, source_label, duplicates = load_cash_by_counterparty(
        source_type="none",
        source_path=None,
    )

    assert cash == {}
    assert audit_rows == []
    assert source_label == "none"
    assert duplicates == []


def test_load_cash_by_counterparty_none_source_type_with_no_path_returns_empty() -> None:
    cash, audit_rows, source_label, duplicates = load_cash_by_counterparty(
        source_type=None,
        source_path=None,
    )

    assert cash == {}
    assert source_label == "none"


def test_load_cash_by_counterparty_invalid_override_schema_raises(tmp_path: Path) -> None:
    source_path = tmp_path / "repo_cash.csv"
    source_path.write_text("counterparty,cash_value\nCIBC,5.0\n", encoding="utf-8")
    bad_overrides = tmp_path / "bad_overrides.csv"
    bad_overrides.write_text("name,amount\nCIBC,9.0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required columns"):
        load_cash_by_counterparty(
            source_type="csv",
            source_path=source_path,
            overrides_path=bad_overrides,
        )


def test_load_cash_by_counterparty_detects_duplicate_names(tmp_path: Path) -> None:
    source_path = tmp_path / "repo_cash.csv"
    source_path.write_text(
        "counterparty,cash_value\nCIBC,5.0\nCIBC,3.0\nASL,2.5\n",
        encoding="utf-8",
    )

    cash, _audit_rows, _label, duplicates = load_cash_by_counterparty(
        source_type="csv",
        source_path=source_path,
    )

    assert "CIBC" in duplicates
    assert cash["CIBC"] == 3.0, "Last value wins on duplicate"


def test_load_cash_by_counterparty_auto_detects_csv_extension(tmp_path: Path) -> None:
    source_path = tmp_path / "repo_cash.csv"
    source_path.write_text("counterparty,cash_value\nCIBC,4.0\n", encoding="utf-8")

    cash, _audit_rows, source_label, _dupes = load_cash_by_counterparty(
        source_type=None,
        source_path=source_path,
    )

    assert cash["CIBC"] == 4.0
    assert source_label.startswith("csv:")


# ---------------------------------------------------------------------------
# find_duplicate_counterparty_names tests
# ---------------------------------------------------------------------------


def test_find_duplicate_counterparty_names_returns_duplicates(tmp_path: Path) -> None:
    source_path = tmp_path / "source.csv"
    source_path.write_text(
        "counterparty,cash_value\nCIBC,1.0\nASL,2.0\nCIBC,3.0\n",
        encoding="utf-8",
    )

    duplicates = find_duplicate_counterparty_names(source_path)

    assert duplicates == ["CIBC"]


def test_find_duplicate_counterparty_names_empty_when_no_duplicates(tmp_path: Path) -> None:
    source_path = tmp_path / "source.csv"
    source_path.write_text(
        "counterparty,cash_value\nCIBC,1.0\nASL,2.0\n",
        encoding="utf-8",
    )

    duplicates = find_duplicate_counterparty_names(source_path)

    assert duplicates == []


def test_load_repo_cash_with_utf8_bom(tmp_path: Path) -> None:
    source_path = tmp_path / "source_bom.csv"
    source_path.write_text(
        "counterparty,cash_value\nCIBC,1.0\nASL,2.0\n",
        encoding="utf-8-sig",
    )

    values = load_repo_cash_structured_source(source_path, source_type="csv")
    assert values["CIBC"] == 1.0
    assert values["ASL"] == 2.0

