"""Checks for macro specification documentation coverage."""

from __future__ import annotations

from pathlib import Path

MACRO_SPEC_PATH = Path("docs/macro_spec.md")
EXPECTED_MACROS = (
    "RunAll_Click",
    "RunExTrend_Click",
    "RunTrend_Click",
    "OpenOutputFolder_Click",
)


def test_macro_spec_doc_exists() -> None:
    assert MACRO_SPEC_PATH.is_file(), "Expected docs/macro_spec.md to exist."


def test_macro_spec_doc_lists_runnerlaunch_macro_intents() -> None:
    content = MACRO_SPEC_PATH.read_text(encoding="utf-8")
    assert (
        "Macro Intent (Plain Language)" in content
    ), "docs/macro_spec.md must include a plain-language macro intent section."

    for macro_name in EXPECTED_MACROS:
        assert f"`{macro_name}`" in content, (
            "docs/macro_spec.md must describe intent for macro "
            f"{macro_name} from assets/vba/RunnerLaunch.bas."
        )


def test_macro_spec_doc_lists_required_inputs_and_output_expectations_per_macro() -> None:
    content = MACRO_SPEC_PATH.read_text(encoding="utf-8")
    assert (
        "Per-Macro Requirements" in content
    ), "docs/macro_spec.md must include a per-macro requirements section."

    required_section_markers = (
        "Required inputs (sheet names, columns):",
        "Output expectations (ranges affected, invariants):",
    )
    for marker in required_section_markers:
        assert marker in content, f"docs/macro_spec.md is missing section marker: {marker}"

    for macro_name in EXPECTED_MACROS:
        macro_section = f"### `{macro_name}`"
        assert macro_section in content, (
            "docs/macro_spec.md must include required inputs and output expectations for "
            f"{macro_name}."
        )

    required_terms = (
        "Runner!B11:B12",
        "CPRS - CH!D10:D20",
        "CPRS - CH!E10:E20",
        "CPRS - CH!C10:C20",
    )
    for term in required_terms:
        assert term in content, (
            "docs/macro_spec.md must include range-level output expectations and invariants; "
            f"missing {term}."
        )


def test_macro_spec_doc_includes_known_acceptable_drift_section() -> None:
    content = MACRO_SPEC_PATH.read_text(encoding="utf-8")
    assert (
        "Known-Acceptable Drift" in content
    ), "docs/macro_spec.md must document known-acceptable drift."
    assert (
        "rel_tol=1e-12" in content and "abs_tol=1e-12" in content
    ), "Known-acceptable drift must include explicit numeric tolerances."
    assert (
        "rounding" in content.lower()
    ), "Known-acceptable drift must include explicit rounding guidance."
