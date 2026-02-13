"""Unit tests for counter_risk configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.config import WorkflowConfig, load_config


def test_load_all_programs_config() -> None:
    config = load_config(Path("config/all_programs.yml"))
    assert isinstance(config, WorkflowConfig)


def test_load_ex_trend_config() -> None:
    config = load_config(Path("config/ex_trend.yml"))
    assert isinstance(config, WorkflowConfig)


def test_load_trend_config() -> None:
    config = load_config(Path("config/trend.yml"))
    assert isinstance(config, WorkflowConfig)


def test_load_config_raises_for_missing_required_fields(tmp_path: Path) -> None:
    bad_config = tmp_path / "missing.yml"
    bad_config.write_text("as_of_date: 2025-12-31\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Configuration validation failed"):
        load_config(bad_config)


def test_load_config_raises_for_invalid_field_types(tmp_path: Path) -> None:
    bad_config = tmp_path / "invalid.yml"
    bad_config.write_text(
        "\n".join(
            [
                "as_of_date: not-a-date",
                "mosers_all_programs_xlsx: 123",
                "mosers_ex_trend_xlsx: docs/N__A Data/MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
                "mosers_trend_xlsx: docs/N__A Data/MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
                "hist_all_programs_3yr_xlsx: docs/Ratings Instructiosns/Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "hist_ex_llc_3yr_xlsx: docs/Ratings Instructiosns/Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "hist_llc_3yr_xlsx: docs/Ratings Instructiosns/Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "monthly_pptx: docs/Ratings Instructiosns/Monthly Counterparty Exposure Report.pptx",
                "output_root: runs/test",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Configuration validation failed"):
        load_config(bad_config)


def test_workflow_config_defaults_screenshot_replacement_fields() -> None:
    config = WorkflowConfig(
        mosers_all_programs_xlsx=Path("a.xlsx"),
        mosers_ex_trend_xlsx=Path("b.xlsx"),
        mosers_trend_xlsx=Path("c.xlsx"),
        hist_all_programs_3yr_xlsx=Path("d.xlsx"),
        hist_ex_llc_3yr_xlsx=Path("e.xlsx"),
        hist_llc_3yr_xlsx=Path("f.xlsx"),
        monthly_pptx=Path("report.pptx"),
    )

    assert config.enable_screenshot_replacement is False
    assert config.screenshot_replacement_implementation == "zip"
    assert config.screenshot_inputs == {}


def test_load_config_raises_for_invalid_screenshot_implementation(tmp_path: Path) -> None:
    bad_config = tmp_path / "invalid_screenshot_impl.yml"
    bad_config.write_text(
        "\n".join(
            [
                "as_of_date: 2025-12-31",
                "mosers_all_programs_xlsx: docs/N__A Data/MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
                "mosers_ex_trend_xlsx: docs/N__A Data/MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
                "mosers_trend_xlsx: docs/N__A Data/MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
                "hist_all_programs_3yr_xlsx: docs/Ratings Instructiosns/Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "hist_ex_llc_3yr_xlsx: docs/Ratings Instructiosns/Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "hist_llc_3yr_xlsx: docs/Ratings Instructiosns/Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "monthly_pptx: docs/Ratings Instructiosns/Monthly Counterparty Exposure Report.pptx",
                "screenshot_replacement_implementation: unsupported-backend",
                "output_root: runs/test",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Configuration validation failed"):
        load_config(bad_config)
