from __future__ import annotations

from datetime import date

from counter_risk.pipeline.run_folder_outputs import build_run_folder_readme_content


def test_build_run_folder_readme_content_includes_expected_filenames_and_steps() -> None:
    content = build_run_folder_readme_content(date(2026, 1, 31))

    assert "Monthly Counterparty Exposure Report (Master) - 2026-01-31.pptx" in content
    assert "Monthly Counterparty Exposure Report - 2026-01-31.pptx" in content
    assert "\n1. " in content
    assert "\n2. " in content
    assert "\n3. " in content

