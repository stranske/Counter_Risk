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
