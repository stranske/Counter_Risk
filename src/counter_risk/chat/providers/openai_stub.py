"""Deterministic local OpenAI provider stub."""

from __future__ import annotations


class OpenAIStubProvider:
    """OpenAI-like deterministic provider implementation with no network calls."""

    def generate(self, messages: list[dict[str, str]], model: str, **kwargs: object) -> str:
        context_answer = str(kwargs.get("context_answer", "No answer available."))
        return f"openai-stub:{model} | {context_answer}"
