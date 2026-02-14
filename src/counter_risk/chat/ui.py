"""UI-facing chat submit helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from counter_risk.chat.context import RunContext
from counter_risk.chat.session import ChatSession, is_provider_model_supported


@dataclass(frozen=True)
class SubmitResult:
    """Result payload for one chat submit action."""

    assistant_message: str | None
    validation_error: str | None


def _build_session(context: RunContext, provider_key: str, model_key: str) -> ChatSession:
    return ChatSession(context=context, provider=provider_key, model=model_key)


def submit_chat_message(
    *,
    context: RunContext,
    user_text: str,
    provider_key: str,
    model_key: str,
    session_factory: Callable[[RunContext, str, str], ChatSession] = _build_session,
) -> SubmitResult:
    """Validate selections and execute one chat turn."""

    message = user_text.strip()
    if not message:
        return SubmitResult(assistant_message=None, validation_error="Message cannot be empty.")

    if not is_provider_model_supported(provider_key, model_key):
        return SubmitResult(
            assistant_message=None,
            validation_error="Select a valid provider and model before submitting.",
        )

    session = session_factory(context, provider_key, model_key)
    answer = session.ask(message)
    return SubmitResult(assistant_message=answer, validation_error=None)
