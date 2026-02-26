"""Integration tests for registry-first normalization and mapping diff output."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import pytest

from counter_risk.normalize import (
    normalize_counterparty_with_source,
    resolve_clearing_house,
    resolve_counterparty,
)
from counter_risk.pipeline.run import reconcile_series_coverage
from counter_risk.reports.mapping_diff import generate_mapping_diff_report


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "fixtures" / name


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


def test_resolve_counterparty_uses_registry_direct_canonical_match_before_fallback(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "name_registry.yml"
    registry_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: soc_gen",
                "    display_name: Soc Gen",
                "    aliases:",
                "      - SG",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    display_name_match = resolve_counterparty("Soc Gen", registry_path=registry_path)
    canonical_key_match = resolve_counterparty("soc_gen", registry_path=registry_path)

    assert display_name_match.canonical_name == "Soc Gen"
    assert display_name_match.source == "registry"
    assert canonical_key_match.canonical_name == "Soc Gen"
    assert canonical_key_match.source == "registry"


def test_resolve_clearing_house_returns_registry_source_when_name_is_in_registry(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "name_registry.yml"
    registry_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: custom_ch",
                "    display_name: Custom Clearing House",
                "    aliases:",
                "      - Custom CH",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    resolution = resolve_clearing_house("Custom CH", registry_path=registry_path)

    assert resolution.canonical_name == "Custom Clearing House"
    assert resolution.source == "registry"


def test_resolve_clearing_house_returns_fallback_source_when_registry_has_no_match(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "name_registry.yml"
    registry_path.write_text("schema_version: 1\nentries: []\n", encoding="utf-8")

    resolution = resolve_clearing_house("ICE Clear US", registry_path=registry_path)

    assert resolution.canonical_name == "ICE"
    assert resolution.source == "fallback"


def test_resolve_clearing_house_unknown_name_uses_identity_with_fallback_source(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "name_registry.yml"
    registry_path.write_text("schema_version: 1\nentries: []\n", encoding="utf-8")

    resolution = resolve_clearing_house("LCH", registry_path=registry_path)

    assert resolution.canonical_name == "LCH"
    assert resolution.source == "fallback"


def test_resolve_clearing_house_handles_missing_registry_without_raising(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "nonexistent_registry.yml"

    resolution = resolve_clearing_house("ICE Clear US", registry_path=missing_path)

    assert resolution.canonical_name == "ICE"
    assert resolution.source == "fallback"


def test_resolve_clearing_house_handles_empty_registry_without_raising(
    tmp_path: Path,
) -> None:
    empty_path = tmp_path / "empty_registry.yml"
    empty_path.write_text("", encoding="utf-8")

    resolution = resolve_clearing_house("ICE Clear US", registry_path=empty_path)

    assert resolution.canonical_name == "ICE"
    assert resolution.source == "fallback"


def test_normalize_counterparty_with_source_exposes_source_attribute(tmp_path: Path) -> None:
    registry_path = tmp_path / "name_registry.yml"
    registry_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: soc_gen",
                "    display_name: Soc Gen",
                "    aliases:",
                "      - SG",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    resolution = normalize_counterparty_with_source("SG", registry_path=registry_path)

    assert resolution.source == "registry"


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


def test_reconciliation_sources_differ_between_before_and_after_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _run_with_fixture(fixture_name: str, run_dir: Path) -> list[str]:
        fixture_path = _fixture_path(fixture_name).resolve()
        config_dir = run_dir / "config"
        config_dir.mkdir(parents=True)
        shutil.copyfile(
            fixture_path,
            config_dir / "name_registry.yml",
        )
        monkeypatch.chdir(run_dir)

        captured_sources: list[str] = []
        original = normalize_counterparty_with_source

        def _capture_source(raw_name: str, **kwargs: Any) -> Any:
            resolution = original(raw_name, **kwargs)
            captured_sources.append(resolution.source)
            return resolution

        monkeypatch.setattr(
            "counter_risk.pipeline.run.normalize_counterparty_with_source",
            _capture_source,
        )
        reconcile_series_coverage(
            parsed_data_by_sheet={
                "Total": {
                    "totals": [{"counterparty": "Societe Generale"}],
                    "futures": [],
                }
            },
            historical_series_headers_by_sheet={"Total": ("Soc Gen Inc",)},
        )
        return captured_sources

    before_sources = _run_with_fixture("name_registry_before.yml", tmp_path / "before")
    after_sources = _run_with_fixture("name_registry_after.yml", tmp_path / "after")

    assert "fallback" in before_sources
    assert "registry" in after_sources
    assert before_sources != after_sources
