"""Tests for chat UI submit wiring."""

from __future__ import annotations

from pathlib import Path

from counter_risk.chat.context import load_run_context
from counter_risk.chat.ui import submit_chat_message


def _write_minimal_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        (
            "{"
            '"as_of_date": "2026-02-13", '
            '"run_date": "2026-02-14T00:00:00+00:00", '
            '"warnings": [], '
            '"top_exposures": {"all_programs": [{"counterparty": "A", "notional": 10.0}]}, '
            '"top_changes_per_variant": {"all_programs": [{"counterparty": "A", "notional_change": 2.5}]}'
            "}"
        ),
        encoding="utf-8",
    )
    return run_dir


def test_submit_chat_message_rejects_invalid_provider_model_before_session_call(
    tmp_path: Path,
) -> None:
    context = load_run_context(_write_minimal_run(tmp_path))
    session_factory_called = False

    def _failing_factory(*_: object) -> object:
        nonlocal session_factory_called
        session_factory_called = True
        raise AssertionError("session_factory should not be called for invalid selections")

    result = submit_chat_message(
        context=context,
        user_text="top exposures",
        provider_key="openai",
        model_key="not-a-real-model",
        session_factory=_failing_factory,  # type: ignore[arg-type]
    )

    assert result.assistant_message is None
    assert "valid provider and model" in (result.validation_error or "")
    assert not session_factory_called
