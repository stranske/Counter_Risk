"""Unit tests for mapping diff report input scanning."""

from __future__ import annotations

from pathlib import Path

from counter_risk.reports.mapping_diff import (
    collect_mapping_diff_findings,
    generate_mapping_diff_report,
)


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

    # Metadata values and values from non-name keys should not appear as resolved names.
    assert "run-123" not in report

    # The reconciliation 'warnings' list content must not be extracted as a counterparty name;
    # check that the verbatim warning string is absent from the UNMAPPED section.
    lines = report.splitlines()
    nr_start = lines.index("NAME_RESOLUTIONS")
    pre_nr = "\n".join(lines[:nr_start])
    assert "raw='Societe Generale'" not in pre_nr

    # The legitimate "Societe Generale" name is still picked up via normalization.
    assert "Societe Generale -> Soc Gen\n" in report


def test_generate_mapping_diff_report_preserves_raw_names(tmp_path: Path) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    report = generate_mapping_diff_report(
        registry_path,
        {
            "normalization": [
                {"counterparty": "  Unknown House  "},
                {"counterparty": "   "},
            ],
        },
    )

    assert "UNMAPPED\n  Unknown House  \n" in report
    assert "Unknown House\n" not in report


def test_generate_mapping_diff_report_fallback_section_is_deterministic(tmp_path: Path) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    report = generate_mapping_diff_report(
        registry_path,
        {
            "normalization": [
                {"counterparty": "Citigroup"},
                {"counterparty": "Bank of America, NA"},
                {"counterparty": "Societe Generale"},
            ],
            "reconciliation": {
                "counterparties_in_data": [
                    "Societe Generale",
                    "Citigroup",
                    "Bank of America, NA",
                ]
            },
        },
    )

    expected_section = "\n".join(
        [
            "FALLBACK_MAPPED",
            "Bank of America, NA -> Bank of America",
            "Citigroup -> Citibank",
            "Societe Generale -> Soc Gen",
            "",
        ]
    )
    assert expected_section in report


def test_generate_mapping_diff_report_suggestions_are_deterministic_title_case(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    report = generate_mapping_diff_report(
        registry_path,
        {
            "normalization": [
                {"counterparty": "aaa holdings"},
                {"counterparty": "zeta llc"},
                {"counterparty": "aaa holdings"},
            ],
            "reconciliation": {
                "counterparties_in_data": [
                    "zeta llc",
                    "aaa holdings",
                ]
            },
        },
    )

    expected_section = "\n".join(
        [
            "SUGGESTIONS",
            "aaa holdings -> Aaa Holdings",
            "zeta llc -> Zeta Llc",
            "",
        ]
    )
    assert expected_section in report


def test_generate_mapping_diff_report_sections_use_required_line_formats(tmp_path: Path) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    report = generate_mapping_diff_report(
        registry_path,
        {
            "normalization": [
                {"counterparty": "UNKNOWN broker"},
                {"counterparty": "Citigroup"},
            ],
            "reconciliation": {"counterparties_in_data": ["UNKNOWN broker"]},
        },
    )

    lines = report.splitlines()
    unmapped_start = lines.index("UNMAPPED")
    fallback_start = lines.index("FALLBACK_MAPPED")
    suggestions_start = lines.index("SUGGESTIONS")
    name_resolutions_start = lines.index("NAME_RESOLUTIONS")

    unmapped_lines = lines[unmapped_start + 1 : fallback_start - 1]
    fallback_lines = lines[fallback_start + 1 : suggestions_start - 1]
    suggestion_lines = lines[suggestions_start + 1 : name_resolutions_start - 1]

    assert unmapped_lines == ["UNKNOWN broker"]
    assert fallback_lines == ["Citigroup -> Citibank"]
    assert suggestion_lines == ["UNKNOWN broker -> Unknown Broker"]


def test_collect_mapping_diff_findings_scans_reconciliation_counterparty_fields(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    findings = collect_mapping_diff_findings(
        registry_path,
        {
            "reconciliation": {
                "counterparties_in_data": ["Citigroup", "LCH"],
                "raw_counterparty_labels": ["Citigroup", "LCH"],
            }
        },
    )

    assert findings["unmapped_raw_names"] == ["LCH"]
    assert findings["fallback_mapped"] == {"Citigroup": "Citibank"}


def test_collect_mapping_diff_findings_includes_name_resolutions(tmp_path: Path) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    findings = collect_mapping_diff_findings(
        registry_path,
        {"normalization": [{"counterparty": "Citigroup"}, {"counterparty": "LCH"}]},
    )

    resolutions = {entry["raw"]: entry for entry in findings["name_resolutions"]}
    assert set(resolutions) == {"Citigroup", "LCH"}

    citi = resolutions["Citigroup"]
    assert citi["display"] == "Citigroup"
    assert citi["canonical_key"] == "Citibank"
    assert citi["mapped"] == "Citibank"
    assert citi["source"] == "fallback"

    lch = resolutions["LCH"]
    assert lch["display"] == "LCH"
    assert lch["canonical_key"] == "LCH"
    assert lch["mapped"] == "LCH"
    assert lch["source"] == "unmapped"


def test_collect_mapping_diff_findings_name_resolutions_includes_registry_hits(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    findings = collect_mapping_diff_findings(
        registry_path,
        {"normalization": [{"counterparty": "Bank of America"}]},
    )

    resolutions = {entry["raw"]: entry for entry in findings["name_resolutions"]}
    boa = resolutions["Bank of America"]
    assert boa["source"] == "registry"
    assert boa["canonical_key"] == "bank_of_america"
    assert boa["mapped"] == "Bank of America"


def test_collect_mapping_diff_findings_name_resolutions_separates_raw_display_key(
    tmp_path: Path,
) -> None:
    """raw preserves original spacing; display collapses whitespace; key also collapses and normalises punctuation."""
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    # Name with leading spaces and a Unicode en-dash
    raw = "  Korea Exchange–Seoul  "
    findings = collect_mapping_diff_findings(
        registry_path,
        {"normalization": [raw]},
    )

    resolutions = {entry["raw"]: entry for entry in findings["name_resolutions"]}
    entry = resolutions[raw]
    assert entry["raw"] == raw
    assert entry["display"] == "Korea Exchange–Seoul"
    assert entry["canonical_key"] == "Korea Exchange-Seoul"


def test_generate_mapping_diff_report_includes_name_resolutions_section(tmp_path: Path) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    report = generate_mapping_diff_report(
        registry_path,
        {"normalization": [{"counterparty": "Citigroup"}, {"counterparty": "Unknown Co"}]},
    )

    assert "NAME_RESOLUTIONS\n" in report
    assert "raw='Citigroup'" in report
    assert "display='Citigroup'" in report
    assert "key='Citibank'" in report
    assert "-> 'Citibank'" in report
    assert "[fallback]" in report
    assert "raw='Unknown Co'" in report
    assert "[unmapped]" in report


def test_generate_mapping_diff_report_name_resolutions_sorted_case_insensitive(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "name_registry.yml"
    _write_registry(registry_path)

    report = generate_mapping_diff_report(
        registry_path,
        {"normalization": ["zeta llc", "aaa holdings"]},
    )

    lines = report.splitlines()
    nr_start = lines.index("NAME_RESOLUTIONS")
    nr_lines = [ln for ln in lines[nr_start + 1 :] if ln]
    assert nr_lines[0].startswith("raw='aaa holdings'")
    assert nr_lines[1].startswith("raw='zeta llc'")
