"""Tests for drop-in template writer scaffolding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from counter_risk.writers.dropin_templates import _build_exposure_index, fill_dropin_template


def test_fill_dropin_template_raises_for_missing_template(tmp_path: Path) -> None:
    missing = tmp_path / "missing-template.xlsx"

    with pytest.raises(FileNotFoundError):
        fill_dropin_template(
            template_path=missing,
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_exposures_type(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(TypeError, match="exposures_df"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=42,
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_build_exposure_index_normalizes_counterparty_and_clearing_house_labels() -> None:
    rows: list[dict[str, Any]] = [
        {"counterparty": "  Societe   Generale "},
        {"clearing_house": " ICE   Clear   U.S. "},
    ]

    indexed = _build_exposure_index(rows)

    assert "soc gen" in indexed
    assert "ice" in indexed


def test_fill_dropin_template_validates_non_empty_path_arguments(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="template_path"):
        fill_dropin_template(
            template_path="",
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_output_suffix(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match="output_path"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xls",
        )


def test_fill_dropin_template_rejects_directory_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="template_path"):
        fill_dropin_template(
            template_path=tmp_path,
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_template_suffix(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xls"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match=r"\.xlsx"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_breakdown_mapping(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(TypeError, match="breakdown"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[],
            breakdown=[],  # type: ignore[arg-type]
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_breakdown_value_type(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match="must be numeric"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[],
            breakdown={"total": "not-a-number"},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_iterable_rows_are_mappings(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(TypeError, match="row at index 0"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[1],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )
