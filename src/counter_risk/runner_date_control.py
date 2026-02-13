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


@dataclass(frozen=True, slots=True)
class RunnerDateControlScope:
    """Scoped decision artifact for the Runner.xlsm date control."""

    requirements: DateControlRequirements
    decision: DateControlDecision
    out_of_scope: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RunnerWorkbookScope:
    """Scope artifact for creating Runner.xlsm with the selected date control."""

    workbook_path: str
    runner_sheet_name: str
    control_data_sheet_name: str
    selector_label_cell: str
    selector_label_text: str
    selector_input_cell: str
    control_data_header_cell: str
    control_data_header_text: str
    control_data_start_row: int
    month_source_start: tuple[int, int]
    month_source_end: tuple[int, int]
    in_scope: tuple[str, ...]
    out_of_scope: tuple[str, ...]


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


def define_runner_xlsm_date_control_scope(
    requirements: DateControlRequirements | None = None,
) -> RunnerDateControlScope:
    """Define scope for Runner.xlsm date control selection from user requirements."""
    effective_requirements = requirements or DateControlRequirements()
    decision = choose_runner_date_input_control(effective_requirements)

    return RunnerDateControlScope(
        requirements=effective_requirements,
        decision=decision,
        out_of_scope=(
            "Run-mode button handlers.",
            "Executable launch integration.",
            "Post-run status and log display.",
        ),
    )


def define_runner_xlsm_workbook_scope(
    requirements: DateControlRequirements | None = None,
) -> RunnerWorkbookScope:
    """Define scope for creating Runner.xlsm with the selected date/month control."""
    control_scope = define_runner_xlsm_date_control_scope(requirements)
    if control_scope.decision.selected_control is not DateInputControl.MONTH_SELECTOR:
        msg = "Current workbook scope supports month-selector control only."
        raise ValueError(msg)

    return RunnerWorkbookScope(
        workbook_path="Runner.xlsm",
        runner_sheet_name="Runner",
        control_data_sheet_name="ControlData",
        selector_label_cell="A3",
        selector_label_text="As-Of Month",
        selector_input_cell="B3",
        control_data_header_cell="A1",
        control_data_header_text="MonthEnd",
        control_data_start_row=2,
        month_source_start=(2020, 1),
        month_source_end=(2035, 12),
        in_scope=(
            "Create Runner.xlsm workbook artifact at repository root.",
            "Create visible Runner sheet with month-selector label and input cell.",
            "Create hidden ControlData sheet with deterministic month-end values.",
            "Bind month selector data validation to ControlData month-end range.",
        ),
        out_of_scope=(
            "Run-mode button handlers.",
            "Executable launch integration.",
            "Post-run status and log display.",
        ),
    )
