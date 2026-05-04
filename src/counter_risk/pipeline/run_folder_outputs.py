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
    distribution_pdf: Path | None = None


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
    distribution_pdf = (
        None if ppt_outputs.distribution_pdf is None else str(ppt_outputs.distribution_pdf)
    )
    send_line = (
        f"2. Send this file to recipients: {distribution_pdf}."
        if distribution_pdf is not None
        else f"2. Send this file to recipients: {distribution}."
    )
    lines = [
        "Counterparty Risk PPT Distribution Guide",
        "",
        f"Maintainer-only file (do not send): {master}",
        f"Recipient file (safe to send): {distribution}",
    ]
    if distribution_pdf is not None:
        lines.append(f"Recipient PDF (preferred when available): {distribution_pdf}")
    lines.extend(
        [
            "",
            "1. Edit only the maintainer Master PPT and keep it inside this run folder.",
            send_line,
            "3. Do not send the Master PPT to recipients.",
        ]
    )

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
