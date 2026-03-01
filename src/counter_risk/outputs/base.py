"""Output generator interface for pluggable pipeline outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

from counter_risk.config import WorkflowConfig


@dataclass(frozen=True)
class OutputContext:
    """Immutable run context passed to output generators."""

    config: WorkflowConfig
    run_dir: Path
    as_of_date: date
    run_date: date
    formatting_profile: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


class OutputGenerator(Protocol):
    """Interface implemented by output plugins."""

    name: str

    def generate(self, *, context: OutputContext) -> tuple[Path, ...]:
        """Generate one output type and return created output paths."""
