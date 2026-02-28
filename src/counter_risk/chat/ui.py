"""UI-facing chat submit helpers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from counter_risk.chat.context import RunContext
from counter_risk.chat.session import (
    ChatSession,
    ChatSessionError,
    PromptInjectionError,
    is_provider_model_supported,
)

_LOGGER = logging.getLogger(__name__)


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

    try:
        session = session_factory(context, provider_key, model_key)
        answer = session.send(message, provider_key=provider_key, model_key=model_key)
    except (ChatSessionError, PromptInjectionError) as exc:
        return SubmitResult(assistant_message=None, validation_error=str(exc))
    except RuntimeError:
        _LOGGER.exception(
            "Chat provider invocation failed for provider=%s model=%s",
            provider_key,
            model_key,
        )
        return SubmitResult(
            assistant_message=None,
            validation_error=(
                "Chat provider call failed. Check provider credentials/connectivity and retry."
            ),
        )
    return SubmitResult(assistant_message=answer, validation_error=None)
