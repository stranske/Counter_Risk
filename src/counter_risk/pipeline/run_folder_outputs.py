"""Helpers for deterministic run-folder operator-facing output text."""

from __future__ import annotations

from datetime import date

from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names


def build_run_folder_readme_content(as_of_date: date) -> str:
    """Build README content for PPT-enabled run folders."""

    output_names = resolve_ppt_output_names(as_of_date)
    lines = [
        "Counterparty Risk PPT Distribution Guide",
        "",
        f"Master PPT: {output_names.master_filename}",
        f"Distribution PPT: {output_names.distribution_filename}",
        "",
        "1. Open the Master PPT and verify linked chart values are refreshed for the as-of date.",
        f"2. Confirm the standalone Distribution PPT is present as '{output_names.distribution_filename}'.",
        "3. Send only the Distribution PPT to recipients and retain the Master PPT in the run folder.",
    ]
    return "\n".join(lines) + "\n"
