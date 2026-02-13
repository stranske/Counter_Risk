"""Validate the Runner month-selector decision scope artifact."""

from __future__ import annotations

from pathlib import Path


def test_month_selector_decision_doc_defines_scope_from_requirements() -> None:
    decision_doc = Path("docs/runner_xlsm_month_selector_decision.md").read_text(encoding="utf-8")

    assert "Use a **month selector** dropdown" in decision_doc
    assert "User Requirements Considered" in decision_doc
    assert "non-technical" in decision_doc
    assert "month-end" in decision_doc
    assert "not uniformly available/reliable" in decision_doc
    assert "deterministic and CI-testable" in decision_doc
    assert "Out Of Scope For This Slice" in decision_doc
