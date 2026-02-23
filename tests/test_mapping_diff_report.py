"""Unit tests for mapping diff report input scanning."""

from __future__ import annotations

from pathlib import Path

from counter_risk.reports.mapping_diff import generate_mapping_diff_report


def _write_registry(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: bank_of_america",
                "    display_name: Bank of America",
                "    aliases:",
                "      - Bank of America",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_generate_mapping_diff_report_scans_normalization_and_reconciliation_payloads(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    report = generate_mapping_diff_report(
        registry_path,
        {
            "normalization": [
                {"counterparty": "Societe Generale", "notional": 1.0},
                {"counterparty": "Unknown House"},
            ],
            "reconciliation": {
                "by_sheet": {
                    "Total": {
                        "counterparties_in_data": [
                            "Bank of America, NA",
                            "Unknown House",
                            "Citigroup",
                        ],
                        "normalized_counterparties_in_data": [
                            "Bank of America",
                            "Unknown House",
                            "Citibank",
                        ],
                    }
                }
            },
        },
    )

    assert "UNMAPPED\nUnknown House\n" in report
    assert "FALLBACK_MAPPED\n" in report
    assert "Bank of America, NA -> Bank of America\n" in report
    assert "Citigroup -> Citibank\n" in report
    assert "Societe Generale -> Soc Gen\n" in report
    assert "SUGGESTIONS\nUnknown House -> Unknown House\n" in report


def test_generate_mapping_diff_report_ignores_non_name_string_fields(tmp_path: Path) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    report = generate_mapping_diff_report(
        registry_path,
        {
            "normalization": {
                "metadata": {"run_id": "run-123"},
                "rows": [{"counterparty": "Societe Generale", "segment": "swaps"}],
            },
            "reconciliation": {"warnings": ["raw='Societe Generale'"]},
        },
    )

    assert "run-123" not in report
    assert "raw='Societe Generale'" not in report
    assert "Societe Generale -> Soc Gen\n" in report
