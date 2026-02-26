"""Helpers for deterministic run-folder operator-facing output text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class RunFolderReadmePptOutputs:
    """Resolved PPT output paths rendered in the run-folder README."""

    master: Path
    distribution: Path


@dataclass(frozen=True)
class RunFolderWarningBanner:
    """Warning banner payload rendered in the run-folder README."""

    title: str
    message: str
    report_path: Path | None = None


def build_run_folder_readme_content(
    as_of_date: date,
    ppt_outputs: RunFolderReadmePptOutputs,
    warning_banner: RunFolderWarningBanner | None = None,
) -> str:
    """Build README content for PPT-enabled run folders."""

    _ = as_of_date
    master = str(ppt_outputs.master)
    distribution = str(ppt_outputs.distribution)
    lines = [
        "Counterparty Risk PPT Distribution Guide",
        "",
        f"Master PPT: {master}",
        f"Distribution PPT: {distribution}",
        "",
        "1. Open the Master PPT and verify linked chart values are refreshed for the as-of date.",
        f"2. Confirm the standalone Distribution PPT is present as '{distribution}'.",
        "3. Send only the Distribution PPT to recipients and retain the Master PPT in the run folder.",
    ]

    if warning_banner is not None:
        lines.extend(
            [
                "",
                f"WARNING: {warning_banner.title}",
                warning_banner.message,
            ]
        )
        if warning_banner.report_path is not None:
            lines.append(f"Review breach details: {warning_banner.report_path}")

    return "\n".join(lines) + "\n"
