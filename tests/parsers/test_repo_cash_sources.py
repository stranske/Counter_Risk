"""Tests for structured Repo Cash source ingestion."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook  # type: ignore[import-untyped]

from counter_risk.parsers.repo_cash_sources import (
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
    source_path = tmp_path / "repo_cash.xlsx"
    workbook = Workbook()
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
