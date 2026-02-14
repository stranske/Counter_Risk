"""Tests for MOSERS template retrieval helpers."""

from __future__ import annotations

from counter_risk.mosers.template import (
    get_mosers_template_bytes,
    get_mosers_template_path,
    load_mosers_template_workbook,
)


def test_get_mosers_template_path_points_to_existing_xlsx() -> None:
    template_path = get_mosers_template_path()

    assert template_path.exists()
    assert template_path.suffix == ".xlsx"


def test_get_mosers_template_bytes_returns_non_empty_payload() -> None:
    template_bytes = get_mosers_template_bytes()

    assert isinstance(template_bytes, bytes)
    assert len(template_bytes) > 0


def test_load_mosers_template_workbook_contains_expected_sheets() -> None:
    workbook = load_mosers_template_workbook()
    try:
        assert "CPRS - CH" in workbook.sheetnames
        assert "CPRS - FCM" in workbook.sheetnames
    finally:
        workbook.close()
