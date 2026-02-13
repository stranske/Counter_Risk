"""Tests for drop-in template writer scaffolding."""

from __future__ import annotations

from pathlib import Path

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
    rows = [
        {"counterparty": "  Societe   Generale "},
        {"clearing_house": " ICE   Clear   U.S. "},
    ]

    indexed = _build_exposure_index(rows)

    assert "soc gen" in indexed
    assert "ice" in indexed
