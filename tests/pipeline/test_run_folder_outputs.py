from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names
from counter_risk.pipeline.run_folder_outputs import (
    RunFolderReadmePptOutputs,
    build_run_folder_readme_content,
)


def test_build_run_folder_readme_content_includes_expected_filenames_and_steps() -> None:
    output_names = resolve_ppt_output_names(date(2026, 1, 31))
    content = build_run_folder_readme_content(
        date(2026, 1, 31),
        RunFolderReadmePptOutputs(
            master=Path(output_names.master_filename),
            distribution=Path(output_names.distribution_filename),
        ),
    )

    assert output_names.master_filename in content
    assert output_names.distribution_filename in content
    assert "\n1. " in content
    assert "\n2. " in content
    assert "\n3. " in content


def test_build_run_folder_readme_content_has_numbered_steps_in_order() -> None:
    output_names = resolve_ppt_output_names(date(2026, 1, 31))
    content = build_run_folder_readme_content(
        date(2026, 1, 31),
        RunFolderReadmePptOutputs(
            master=Path(output_names.master_filename),
            distribution=Path(output_names.distribution_filename),
        ),
    )

    step_1 = re.search(r"^1\.\s", content, flags=re.MULTILINE)
    step_2 = re.search(r"^2\.\s", content, flags=re.MULTILINE)
    step_3 = re.search(r"^3\.\s", content, flags=re.MULTILINE)

    assert step_1 is not None
    assert step_2 is not None
    assert step_3 is not None
    assert step_1.start() < step_2.start() < step_3.start()
