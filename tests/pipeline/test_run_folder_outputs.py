from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names
from counter_risk.pipeline.run_folder_outputs import (
    RunFolderReadmePptOutputs,
    RunFolderWarningBanner,
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
    assert "Maintainer-only file (do not send):" in content
    assert "Recipient file (safe to send):" in content
    assert "Do not send the Master PPT to recipients." in content


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
    assert "WARNING:" not in content


def test_build_run_folder_readme_content_includes_limit_warning_banner_when_provided() -> None:
    output_names = resolve_ppt_output_names(date(2026, 1, 31))
    content = build_run_folder_readme_content(
        date(2026, 1, 31),
        RunFolderReadmePptOutputs(
            master=Path(output_names.master_filename),
            distribution=Path(output_names.distribution_filename),
        ),
        warning_banner=RunFolderWarningBanner(
            title="Limit Breaches Detected (2)",
            message="Warning banner: 2 configured limit breaches were detected.",
            report_path=Path("limit_breaches.csv"),
        ),
    )

    assert "WARNING: Limit Breaches Detected (2)" in content
    assert "Warning banner: 2 configured limit breaches were detected." in content
    assert "Review breach details: limit_breaches.csv" in content


def test_build_run_folder_readme_content_prefers_distribution_pdf_when_available() -> None:
    output_names = resolve_ppt_output_names(date(2026, 1, 31))
    distribution_pdf = Path(output_names.distribution_filename.replace(".pptx", ".pdf"))
    content = build_run_folder_readme_content(
        date(2026, 1, 31),
        RunFolderReadmePptOutputs(
            master=Path(output_names.master_filename),
            distribution=Path(output_names.distribution_filename),
            distribution_pdf=distribution_pdf,
        ),
    )

    assert f"Recipient PDF (preferred when available): {distribution_pdf}" in content
    assert f"Send this file to recipients: {distribution_pdf}." in content
