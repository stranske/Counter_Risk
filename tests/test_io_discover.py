"""Tests for input discovery from known directory roots."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from counter_risk.config import InputDiscoveryConfig
from counter_risk.io.discover import (
    DiscoveryMatch,
    DiscoveryResult,
    discover_daily_holdings_pdf_files,
    discover_exposure_summary_files,
    discover_input_candidates,
    discover_raw_nisa_monthly_files,
    discover_templates_and_historical_files,
    resolve_discovery_selections,
)


def test_discover_module_supports_date_pattern_matching(tmp_path: Path) -> None:
    monthly_root = tmp_path / "monthly"
    historical_root = tmp_path / "historical"
    template_root = tmp_path / "templates"
    for root in (monthly_root, historical_root, template_root):
        root.mkdir(parents=True)

    (monthly_root / "NISA Monthly All Programs - Raw.xlsx").write_text("x", encoding="utf-8")
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "Daily Holdings 2025-12-31.pdf").write_text("x", encoding="utf-8")
    (historical_root / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (historical_root / "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (historical_root / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (template_root / "Monthly Counterparty Exposure Report.pptx").write_text("x", encoding="utf-8")

    discovery_config = InputDiscoveryConfig(
        directory_roots={
            "monthly_inputs": monthly_root,
            "historical_inputs": historical_root,
            "template_inputs": template_root,
        },
        naming_patterns={
            "raw_nisa_all_programs_xlsx": ["NISA Monthly All Programs - Raw.xlsx"],
            "mosers_all_programs_xlsx": [
                "MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - All Programs.xlsx"
            ],
            "mosers_ex_trend_xlsx": [
                "MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - Ex Trend.xlsx"
            ],
            "mosers_trend_xlsx": [
                "MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - Trend.xlsx"
            ],
            "daily_holdings_pdf": ["Daily Holdings {as_of_date}.pdf"],
            "hist_all_programs_3yr_xlsx": [
                "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
            ],
            "hist_ex_llc_3yr_xlsx": ["Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx"],
            "hist_llc_3yr_xlsx": ["Historical Counterparty Risk Graphs - LLC 3 Year.xlsx"],
            "monthly_pptx": ["Monthly Counterparty Exposure Report*.pptx"],
        },
    )

    as_of = date(2025, 12, 31)
    raw_matches = discover_raw_nisa_monthly_files(discovery_config, as_of_date=as_of)
    assert [match.path.name for match in raw_matches] == ["NISA Monthly All Programs - Raw.xlsx"]

    exposure_matches = discover_exposure_summary_files(discovery_config, as_of_date=as_of)
    assert [match.path.name for match in exposure_matches["mosers_all_programs_xlsx"]] == [
        "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx"
    ]
    assert [match.path.name for match in exposure_matches["mosers_ex_trend_xlsx"]] == [
        "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx"
    ]
    assert [match.path.name for match in exposure_matches["mosers_trend_xlsx"]] == [
        "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx"
    ]

    daily_holdings_matches = discover_daily_holdings_pdf_files(discovery_config, as_of_date=as_of)
    assert [match.path.name for match in daily_holdings_matches] == [
        "Daily Holdings 2025-12-31.pdf"
    ]

    template_and_hist_matches = discover_templates_and_historical_files(
        discovery_config,
        as_of_date=as_of,
    )
    assert [match.path.name for match in template_and_hist_matches["monthly_pptx"]] == [
        "Monthly Counterparty Exposure Report.pptx"
    ]
    assert [
        match.path.name for match in template_and_hist_matches["hist_all_programs_3yr_xlsx"]
    ] == ["Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"]
    assert [match.path.name for match in template_and_hist_matches["hist_ex_llc_3yr_xlsx"]] == [
        "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx"
    ]
    assert [match.path.name for match in template_and_hist_matches["hist_llc_3yr_xlsx"]] == [
        "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx"
    ]


def test_discover_input_candidates_returns_multiple_matches(tmp_path: Path) -> None:
    template_root = tmp_path / "templates"
    template_root.mkdir(parents=True)
    (template_root / "Monthly Counterparty Exposure Report.pptx").write_text("x", encoding="utf-8")
    (template_root / "Monthly Counterparty Exposure Report - v2.pptx").write_text(
        "x", encoding="utf-8"
    )

    discovery_config = InputDiscoveryConfig(
        directory_roots={"template_inputs": template_root},
        naming_patterns={"monthly_pptx": ["Monthly Counterparty Exposure Report*.pptx"]},
    )

    result = discover_input_candidates(
        discovery_config,
        as_of_date=date(2025, 12, 31),
        input_names=("monthly_pptx",),
    )

    assert [match.path.name for match in result.matches_by_input["monthly_pptx"]] == [
        "Monthly Counterparty Exposure Report - v2.pptx",
        "Monthly Counterparty Exposure Report.pptx",
    ]


def test_discover_input_candidates_filters_invalid_file_types(tmp_path: Path) -> None:
    monthly_root = tmp_path / "monthly"
    monthly_root.mkdir(parents=True)
    (monthly_root / "Daily Holdings 2025-12-31.txt").write_text("x", encoding="utf-8")

    discovery_config = InputDiscoveryConfig(
        directory_roots={"monthly_inputs": monthly_root},
        naming_patterns={"daily_holdings_pdf": ["Daily Holdings*.txt"]},
    )

    result = discover_input_candidates(
        discovery_config,
        as_of_date=date(2025, 12, 31),
        input_names=("daily_holdings_pdf",),
    )

    assert result.matches_by_input["daily_holdings_pdf"] == ()


def test_resolve_discovery_selections_auto_selects_single_match(tmp_path: Path) -> None:
    file_a = tmp_path / "file_a.xlsx"
    file_a.write_text("x", encoding="utf-8")

    result = DiscoveryResult(
        matches_by_input={
            "mosers_ex_trend_xlsx": (
                DiscoveryMatch(
                    input_name="mosers_ex_trend_xlsx",
                    path=file_a,
                    root_name="monthly_inputs",
                    pattern="*.xlsx",
                ),
            ),
        }
    )

    selected = resolve_discovery_selections(result)

    assert selected == {"mosers_ex_trend_xlsx": file_a}


def test_resolve_discovery_selections_prompts_on_multiple_matches(tmp_path: Path) -> None:
    file_a = tmp_path / "Report.pptx"
    file_b = tmp_path / "Report - v2.pptx"
    file_a.write_text("x", encoding="utf-8")
    file_b.write_text("x", encoding="utf-8")

    matches = (
        DiscoveryMatch(
            input_name="monthly_pptx",
            path=file_a,
            root_name="template_inputs",
            pattern="Report*.pptx",
        ),
        DiscoveryMatch(
            input_name="monthly_pptx",
            path=file_b,
            root_name="template_inputs",
            pattern="Report*.pptx",
        ),
    )
    result = DiscoveryResult(matches_by_input={"monthly_pptx": matches})

    # Simulate user picking the second option
    def fake_prompt(input_name: str, candidates: tuple[DiscoveryMatch, ...]) -> DiscoveryMatch:
        return candidates[1]

    selected = resolve_discovery_selections(result, prompt_fn=fake_prompt)

    assert selected == {"monthly_pptx": file_b}


def test_resolve_discovery_selections_omits_inputs_with_no_matches() -> None:
    result = DiscoveryResult(matches_by_input={"raw_nisa_all_programs_xlsx": ()})

    selected = resolve_discovery_selections(result)

    assert selected == {}
