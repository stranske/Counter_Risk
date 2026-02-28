"""Tests for chat UI submit wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.chat import session as session_module
from counter_risk.chat.context import load_run_context
from counter_risk.chat.session import ChatSession
from counter_risk.chat.ui import submit_chat_message

_MODEL_KEY = "chat-model-placeholder"


@pytest.fixture(autouse=True)
def _provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("CLAUDE_API_STRANSKE", "test-token")


def _provider_model(provider: str) -> str:
    models = session_module.get_provider_models()[provider]
    assert models
    return models[0]


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


def test_submit_chat_message_rejects_invalid_provider_before_send_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = load_run_context(_write_minimal_run(tmp_path))
    send_called = False

    def _failing_send(
        self: ChatSession,
        question: str,
        *,
        provider_key: str,
        model_key: str,
    ) -> str:
        nonlocal send_called
        send_called = True
        raise AssertionError("ChatSession.send should not be called for invalid provider selection")

    monkeypatch.setattr(ChatSession, "send", _failing_send)

    result = submit_chat_message(
        context=context,
        user_text="top exposures",
        provider_key="not-a-provider",
        model_key=_MODEL_KEY,
    )

    assert result.assistant_message is None
    assert "valid provider and model" in (result.validation_error or "")
    assert not send_called


def test_submit_chat_message_calls_send_once_with_selected_provider_and_model(
    tmp_path: Path,
) -> None:
    context = load_run_context(_write_minimal_run(tmp_path))
    send_calls: list[tuple[str, str, str]] = []
    openai_model = _provider_model("openai")

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
        model_key=openai_model,
        session_factory=_session_factory,  # type: ignore[arg-type]
    )

    assert send_calls == [("top exposures", "openai", openai_model)]
    assert result.validation_error is None
    assert result.assistant_message == f"assistant:openai:{openai_model}:top exposures"


def test_submit_chat_message_uses_default_chat_session_and_calls_send_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = load_run_context(_write_minimal_run(tmp_path))
    send_calls: list[tuple[str, str, str]] = []
    openai_model = _provider_model("openai")

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
        model_key=openai_model,
    )

    assert send_calls == [("top exposures", "openai", openai_model)]
    assert result.validation_error is None
    assert result.assistant_message == f"spy:openai:{openai_model}:top exposures"


@pytest.mark.parametrize(
    ("provider_key", "provider_marker"),
    (("openai", "openai-mock"), ("anthropic", "anthropic-mock")),
)
def test_submit_chat_message_renders_provider_response_in_transcript(
    tmp_path: Path,
    provider_key: str,
    provider_marker: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = load_run_context(_write_minimal_run(tmp_path))
    model_key = _provider_model(provider_key)

    class _DeterministicProvider:
        def __init__(self, marker: str) -> None:
            self._marker = marker

        def generate(self, messages: list[dict[str, str]], model: str, **kwargs: object) -> str:
            context_answer = str(kwargs.get("context_answer", "No answer available."))
            return f"{self._marker}:{model} | {context_answer}"

    monkeypatch.setitem(
        session_module._PROVIDER_CLIENTS, provider_key, _DeterministicProvider(provider_marker)
    )

    result = submit_chat_message(
        context=context,
        user_text="top exposures",
        provider_key=provider_key,
        model_key=model_key,
    )

    assert result.validation_error is None
    assert result.assistant_message is not None
    assert f"{provider_marker}:{model_key}" in result.assistant_message


def test_submit_chat_message_returns_error_when_provider_call_fails(tmp_path: Path) -> None:
    context = load_run_context(_write_minimal_run(tmp_path))
    openai_model = _provider_model("openai")

    class _FailingSession:
        def send(self, question: str, *, provider_key: str, model_key: str) -> str:
            _ = (question, provider_key, model_key)
            raise RuntimeError("rate limit exceeded")

    def _session_factory(*_: object) -> _FailingSession:
        return _FailingSession()

    result = submit_chat_message(
        context=context,
        user_text="top exposures",
        provider_key="openai",
        model_key=openai_model,
        session_factory=_session_factory,  # type: ignore[arg-type]
    )

    assert result.assistant_message is None
    assert result.validation_error is not None
    assert "rate limit exceeded" in result.validation_error
