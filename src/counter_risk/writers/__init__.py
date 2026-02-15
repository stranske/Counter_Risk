"""Writer modules for Counter Risk output artifacts."""

from __future__ import annotations

from counter_risk.writers.dropin_templates import fill_dropin_template
from counter_risk.writers.historical_update import (
    append_row_all_programs,
    append_row_ex_trend,
    append_row_trend,
)
from counter_risk.writers.mosers_workbook import (
    generate_mosers_workbook,
    generate_mosers_workbook_ex_trend,
    generate_mosers_workbook_trend,
)
from counter_risk.writers.pptx_screenshots import replace_screenshot_pictures

__all__ = [
    "append_row_all_programs",
    "append_row_ex_trend",
    "append_row_trend",
    "fill_dropin_template",
    "generate_mosers_workbook",
    "generate_mosers_workbook_ex_trend",
    "generate_mosers_workbook_trend",
    "replace_screenshot_pictures",
]
