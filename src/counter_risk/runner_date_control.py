"""Policy for selecting Runner.xlsm date input controls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DateInputControl(StrEnum):
    """Supported Runner date-input control types."""

    MONTH_SELECTOR = "month_selector"
    DATE_PICKER = "date_picker"


@dataclass(frozen=True, slots=True)
class DateControlRequirements:
    """User requirements that drive control selection."""

    non_technical_operator_flow: bool = True
    month_end_reporting_process: bool = True
    cross_office_reliability_required: bool = True
    deterministic_ci_testability_required: bool = True


@dataclass(frozen=True, slots=True)
class DateControlDecision:
    """Decision payload used by docs/tests/build tooling."""

    selected_control: DateInputControl
    rationale: tuple[str, ...]


def choose_runner_date_input_control(
    requirements: DateControlRequirements,
) -> DateControlDecision:
    """Choose a Runner date input control based on explicit requirements."""
    if (
        requirements.non_technical_operator_flow
        and requirements.month_end_reporting_process
        and requirements.cross_office_reliability_required
        and requirements.deterministic_ci_testability_required
    ):
        return DateControlDecision(
            selected_control=DateInputControl.MONTH_SELECTOR,
            rationale=(
                "Monthly as_of_date workflow aligns to month-end selection.",
                "Date picker support is inconsistent across Office environments.",
                "Validation-list month selector is deterministic and CI-testable.",
            ),
        )

    return DateControlDecision(
        selected_control=DateInputControl.DATE_PICKER,
        rationale=(
            "Requirements do not mandate the month-end/reliability/testability constraints.",
        ),
    )
