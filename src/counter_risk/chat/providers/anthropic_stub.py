"""Deterministic local Anthropic provider stub."""

from __future__ import annotations


class AnthropicStubProvider:
    """Anthropic-like deterministic provider implementation with no network calls."""

    def generate(self, messages: list[dict[str, str]], model: str, **kwargs: object) -> str:
        context_answer = str(kwargs.get("context_answer", "No answer available."))
        return f"anthropic-stub:{model} | {context_answer}"
