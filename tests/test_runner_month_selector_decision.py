"""Validate the Runner month-selector decision scope artifact."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.runner_date_control import (
    DateControlRequirements,
    DateInputControl,
    choose_runner_date_input_control,
)


def test_month_selector_decision_doc_defines_scope_from_requirements() -> None:
    decision_doc = Path("docs/runner_xlsm_month_selector_decision.md").read_text(encoding="utf-8")

    assert "Use a **month selector** dropdown" in decision_doc
    assert "User Requirements Considered" in decision_doc
    assert "non-technical" in decision_doc
    assert "month-end" in decision_doc
    assert "not uniformly available/reliable" in decision_doc
    assert "deterministic and CI-testable" in decision_doc
    assert "Out Of Scope For This Slice" in decision_doc


def test_default_runner_requirements_choose_month_selector() -> None:
    decision = choose_runner_date_input_control(DateControlRequirements())
    assert decision.selected_control is DateInputControl.MONTH_SELECTOR
    assert any("month-end" in reason.lower() for reason in decision.rationale)


def test_relaxed_requirements_can_choose_date_picker() -> None:
    relaxed = DateControlRequirements(
        month_end_reporting_process=False,
        cross_office_reliability_required=False,
        deterministic_ci_testability_required=False,
    )
    decision = choose_runner_date_input_control(relaxed)
    assert decision.selected_control is DateInputControl.DATE_PICKER


@pytest.mark.parametrize(
    "override",
    [
        {"non_technical_operator_flow": False},
        {"month_end_reporting_process": False},
        {"cross_office_reliability_required": False},
        {"deterministic_ci_testability_required": False},
    ],
)
def test_any_missing_mandatory_requirement_switches_to_date_picker(
    override: dict[str, bool],
) -> None:
    requirements = DateControlRequirements(**override)
    decision = choose_runner_date_input_control(requirements)
    assert decision.selected_control is DateInputControl.DATE_PICKER
