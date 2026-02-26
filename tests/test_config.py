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
                "run_date: not-a-date",
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


def test_load_config_parses_optional_run_date(tmp_path: Path) -> None:
    config_path = tmp_path / "with_run_date.yml"
    config_path.write_text(
        "\n".join(
            [
                "as_of_date: 2025-12-31",
                "run_date: 2026-01-05",
                "mosers_all_programs_xlsx: docs/N__A Data/MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
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

    config = load_config(config_path)
    assert config.as_of_date is not None
    assert config.as_of_date.isoformat() == "2025-12-31"
    assert config.run_date is not None
    assert config.run_date.isoformat() == "2026-01-05"


def test_load_config_allows_absent_optional_dates(tmp_path: Path) -> None:
    config_path = tmp_path / "without_optional_dates.yml"
    config_path.write_text(
        "\n".join(
            [
                "mosers_all_programs_xlsx: docs/N__A Data/MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
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

    config = load_config(config_path)
    assert config.as_of_date is None
    assert config.run_date is None


def test_load_config_treats_blank_optional_dates_as_none(tmp_path: Path) -> None:
    config_path = tmp_path / "blank_optional_dates.yml"
    config_path.write_text(
        "\n".join(
            [
                'as_of_date: ""',
                'run_date: "   "',
                "mosers_all_programs_xlsx: docs/N__A Data/MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
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

    config = load_config(config_path)
    assert config.as_of_date is None
    assert config.run_date is None


def test_load_config_raises_for_invalid_run_date_format(tmp_path: Path) -> None:
    bad_config = tmp_path / "invalid_run_date.yml"
    bad_config.write_text(
        "\n".join(
            [
                "as_of_date: 2025-12-31",
                "run_date: 2026-01-05T00:00:00Z",
                "mosers_all_programs_xlsx: docs/N__A Data/MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
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


def test_load_config_raises_for_invalid_as_of_date_format(tmp_path: Path) -> None:
    bad_config = tmp_path / "invalid_as_of_date.yml"
    bad_config.write_text(
        "\n".join(
            [
                "as_of_date: 01/31/2026",
                "run_date: 2026-01-31",
                "mosers_all_programs_xlsx: docs/N__A Data/MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
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
    assert config.export_pdf is False
    assert config.screenshot_replacement_implementation == "zip"
    assert config.screenshot_inputs == {}
    assert config.input_discovery.directory_roots == {}
    assert config.input_discovery.naming_patterns == {}
    assert config.reconciliation.fail_policy == "warn"
    assert config.reconciliation.expected_segments_by_variant == {}
    assert config.ppt_output_enabled is True
    assert [entry.name for entry in config.output_generators] == [
        "historical_workbook",
        "ppt_screenshot",
        "ppt_link_refresh",
        "pdf_export",
    ]


def test_load_config_accepts_output_generator_registration(tmp_path: Path) -> None:
    config_path = tmp_path / "output_generators.yml"
    config_path.write_text(
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
                "output_root: runs/test",
                "output_generators:",
                "  - name: ppt_screenshot",
                "    registration: builtin:ppt_screenshot",
                "    stage: ppt_master",
                "    enabled: true",
                "  - name: custom_manifest_stub",
                "    registration: tests.test_pipeline_run_outputs:_ConfigRegisteredOutputGenerator",
                "    stage: ppt_post_distribution",
                "    enabled: false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert len(config.output_generators) == 2
    assert config.output_generators[1].registration.endswith(":_ConfigRegisteredOutputGenerator")


def test_load_config_rejects_duplicate_output_generator_names(tmp_path: Path) -> None:
    config_path = tmp_path / "duplicate_output_generators.yml"
    config_path.write_text(
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
                "output_generators:",
                "  - name: ppt_screenshot",
                "    registration: builtin:ppt_screenshot",
                "    stage: ppt_master",
                "  - name: PPT_SCREENSHOT",
                "    registration: builtin:ppt_screenshot",
                "    stage: ppt_master",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate name"):
        load_config(config_path)


def test_workflow_config_ppt_output_enabled_reflects_flag() -> None:
    enabled_config = WorkflowConfig(
        mosers_all_programs_xlsx=Path("a.xlsx"),
        mosers_ex_trend_xlsx=Path("b.xlsx"),
        mosers_trend_xlsx=Path("c.xlsx"),
        hist_all_programs_3yr_xlsx=Path("d.xlsx"),
        hist_ex_llc_3yr_xlsx=Path("e.xlsx"),
        hist_llc_3yr_xlsx=Path("f.xlsx"),
        monthly_pptx=Path("report.pptx"),
        enable_ppt_output=True,
    )
    disabled_config = enabled_config.model_copy(update={"enable_ppt_output": False})

    assert enabled_config.ppt_output_enabled is True
    assert disabled_config.ppt_output_enabled is False


def test_load_config_accepts_export_pdf_flag(tmp_path: Path) -> None:
    config_path = tmp_path / "with_export_pdf.yml"
    config_path.write_text(
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
                "output_root: runs/test",
                "export_pdf: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert config.export_pdf is True


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


def test_load_config_accepts_reconciliation_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "reconciliation.yml"
    config_path.write_text(
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
                "output_root: runs/test",
                "reconciliation:",
                "  fail_policy: strict",
                "  expected_segments_by_variant:",
                "    all_programs: [swaps, repo, futures_cdx]",
                "    ex_trend: [swaps, repo]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.reconciliation.fail_policy == "strict"
    assert config.reconciliation.expected_segments_by_variant == {
        "all_programs": ["swaps", "repo", "futures_cdx"],
        "ex_trend": ["swaps", "repo"],
    }


def test_load_config_rejects_invalid_reconciliation_fail_policy(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid_reconciliation.yml"
    config_path.write_text(
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
                "output_root: runs/test",
                "reconciliation:",
                "  fail_policy: explode",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Configuration validation failed"):
        load_config(config_path)


def test_load_config_accepts_input_discovery_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "input_discovery.yml"
    config_path.write_text(
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
                "output_root: runs/test",
                "input_discovery:",
                "  directory_roots:",
                "    monthly_inputs: docs/N__A Data",
                "    historical_inputs: docs/Ratings Instructiosns",
                "  naming_patterns:",
                "    mosers_all_programs_xlsx:",
                "      - MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - All Programs.xlsx",
                "    monthly_pptx:",
                "      - Monthly Counterparty Exposure Report*.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert config.input_discovery.directory_roots == {
        "monthly_inputs": Path("docs/N__A Data"),
        "historical_inputs": Path("docs/Ratings Instructiosns"),
    }
    assert config.input_discovery.naming_patterns == {
        "mosers_all_programs_xlsx": [
            "MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - All Programs.xlsx"
        ],
        "monthly_pptx": ["Monthly Counterparty Exposure Report*.pptx"],
    }


def test_load_config_rejects_input_discovery_with_non_list_patterns(tmp_path: Path) -> None:
    config_path = tmp_path / "bad_input_discovery_patterns.yml"
    config_path.write_text(
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
                "output_root: runs/test",
                "input_discovery:",
                "  naming_patterns:",
                "    mosers_all_programs_xlsx: MOSERS Counterparty Risk Summary*.xlsx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Configuration validation failed"):
        load_config(config_path)
