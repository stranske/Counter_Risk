"""Tests for chat UI submit wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.chat.context import load_run_context
from counter_risk.chat.session import ChatSession
from counter_risk.chat.ui import submit_chat_message

_MODEL_KEY = "chat-model-placeholder"


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


def test_submit_chat_message_calls_send_once_with_selected_provider_and_model(
    tmp_path: Path,
) -> None:
    context = load_run_context(_write_minimal_run(tmp_path))
    send_calls: list[tuple[str, str, str]] = []

    class _FakeSession:
        def send(self, question: str, *, provider_key: str, model_key: str) -> str:
            send_calls.append((question, provider_key, model_key))
            return f"assistant:{provider_key}:{model_key}:{question}"

    def _session_factory(*_: object) -> _FakeSession:
        return _FakeSession()

    result = submit_chat_message(
        context=context,
        user_text=" top exposures ",
        provider_key="openai",
        model_key=_MODEL_KEY,
        session_factory=_session_factory,  # type: ignore[arg-type]
    )

    assert send_calls == [("top exposures", "openai", _MODEL_KEY)]
    assert result.validation_error is None
    assert result.assistant_message == "assistant:openai:chat-model-placeholder:top exposures"


def test_submit_chat_message_uses_default_chat_session_and_calls_send_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = load_run_context(_write_minimal_run(tmp_path))
    send_calls: list[tuple[str, str, str]] = []

    def _spy_send(
        self: ChatSession,
        question: str,
        *,
        provider_key: str,
        model_key: str,
    ) -> str:
        send_calls.append((question, provider_key, model_key))
        return f"spy:{provider_key}:{model_key}:{question}"

    monkeypatch.setattr(ChatSession, "send", _spy_send)

    result = submit_chat_message(
        context=context,
        user_text=" top exposures ",
        provider_key="openai",
        model_key=_MODEL_KEY,
    )

    assert send_calls == [("top exposures", "openai", _MODEL_KEY)]
    assert result.validation_error is None
    assert result.assistant_message == "spy:openai:chat-model-placeholder:top exposures"


@pytest.mark.parametrize(
    ("provider_key", "provider_marker"),
    (("openai", "openai-stub"), ("anthropic", "anthropic-stub")),
)
def test_submit_chat_message_renders_stub_provider_response_in_transcript(
    tmp_path: Path,
    provider_key: str,
    provider_marker: str,
) -> None:
    context = load_run_context(_write_minimal_run(tmp_path))

    result = submit_chat_message(
        context=context,
        user_text="top exposures",
        provider_key=provider_key,
        model_key=_MODEL_KEY,
    )

    assert result.validation_error is None
    assert result.assistant_message is not None
    assert f"{provider_marker}:chat-model-placeholder" in result.assistant_message
