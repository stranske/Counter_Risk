"""Integration tests for registry-first normalization and mapping diff output."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from counter_risk.pipeline.run import reconcile_series_coverage
from counter_risk.reports.mapping_diff import generate_mapping_diff_report


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures") / name


def _input_sources() -> dict[str, object]:
    return {
        "normalization": [{"counterparty": "Societe Generale"}],
        "reconciliation": {"counterparties_in_data": ["Societe Generale"]},
    }


def test_mapping_diff_report_before_registry_alias_uses_fallback_section() -> None:
    report = generate_mapping_diff_report(
        _fixture_path("name_registry_before.yml"), _input_sources()
    )

    assert "FALLBACK_MAPPED\nSociete Generale -> Soc Gen\n" in report


def test_mapping_diff_report_after_registry_alias_removes_fallback_and_unmapped_entries() -> None:
    report = generate_mapping_diff_report(
        _fixture_path("name_registry_after.yml"), _input_sources()
    )

    assert "Societe Generale -> Soc Gen\n" not in report
    assert "UNMAPPED\nSociete Generale\n" not in report
    assert "SUGGESTIONS\nSociete Generale -> Societe Generale\n" not in report


def test_mapping_diff_report_changes_between_before_and_after_registry_states() -> None:
    before_report = generate_mapping_diff_report(
        _fixture_path("name_registry_before.yml"),
        _input_sources(),
    )
    after_report = generate_mapping_diff_report(
        _fixture_path("name_registry_after.yml"),
        _input_sources(),
    )

    assert before_report != after_report
    assert "Societe Generale -> Soc Gen\n" in before_report
    assert "Societe Generale -> Soc Gen\n" not in after_report


def test_reconciliation_with_after_registry_has_no_societe_generale_warning(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    shutil.copyfile(
        _fixture_path("name_registry_after.yml"),
        config_dir / "name_registry.yml",
    )
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.WARNING)

    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {"totals": [{"counterparty": "Societe Generale"}], "futures": []}
        },
        historical_series_headers_by_sheet={"Total": ("Soc Gen Inc", "Legacy Counterparty")},
    )

    assert result["warnings"]
    assert not any("Societe Generale" in warning for warning in result["warnings"])
    assert all("Societe Generale" not in record.getMessage() for record in caplog.records)
