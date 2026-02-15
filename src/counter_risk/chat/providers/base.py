"""Provider client abstraction for chat generation."""

from __future__ import annotations

from typing import Protocol


class ProviderClient(Protocol):
    """Interface for pluggable chat providers."""

    def generate(self, messages: list[dict[str, str]], model: str, **kwargs: object) -> str:
        """Return provider text for a prepared messages list and selected model."""
