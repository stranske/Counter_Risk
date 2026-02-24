from __future__ import annotations

import re
from datetime import date

from counter_risk.pipeline.run_folder_outputs import build_run_folder_readme_content


def test_readme_content_includes_filenames_and_three_numbered_steps_in_order() -> None:
    content = build_run_folder_readme_content(date(2026, 1, 31))

    assert "Monthly Counterparty Exposure Report (Master) - 2026-01-31.pptx" in content
    assert "Monthly Counterparty Exposure Report - 2026-01-31.pptx" in content

    step_1 = re.search(r"^1\.", content, flags=re.MULTILINE)
    step_2 = re.search(r"^2\.", content, flags=re.MULTILINE)
    step_3 = re.search(r"^3\.", content, flags=re.MULTILINE)

    assert step_1 is not None
    assert step_2 is not None
    assert step_3 is not None
    assert step_1.start() < step_2.start() < step_3.start()
