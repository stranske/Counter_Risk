"""Config-driven output generator registry."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from counter_risk.config import OutputGeneratorConfig
from counter_risk.outputs.base import OutputGenerator

_OUTPUT_REGISTRATION_PREFIX = "builtin:"


@dataclass(frozen=True)
class OutputGeneratorRegistryContext:
    """Dependencies used while constructing configured output generators."""

    warnings: list[str]
    parsed_by_variant: Mapping[str, Mapping[str, Any]] | None = None
    source_pptx: Path | None = None


_OutputGeneratorFactory = Callable[[OutputGeneratorRegistryContext], OutputGenerator]


class OutputGeneratorRegistry:
    """Load and instantiate output generators declared in workflow config."""

    def __init__(self, *, builtin_factories: Mapping[str, _OutputGeneratorFactory]) -> None:
        self._builtin_factories = dict(builtin_factories)

    def load(
        self,
        *,
        output_generators: Iterable[OutputGeneratorConfig],
        stage: str,
        context: OutputGeneratorRegistryContext,
    ) -> tuple[OutputGenerator, ...]:
        loaded: list[OutputGenerator] = []
        for registration in output_generators:
            if not registration.enabled or registration.stage != stage:
                continue
            loaded.append(self._create(registration=registration, context=context))
        return tuple(loaded)

    def _create(
        self, *, registration: OutputGeneratorConfig, context: OutputGeneratorRegistryContext
    ) -> OutputGenerator:
        generator = self._create_from_registration(
            registration=registration.registration,
            context=context,
        )
        generated_name = str(getattr(generator, "name", "")).strip()
        if generated_name and generated_name != registration.name:
            raise ValueError(
                "Configured output generator name does not match implementation name "
                f"({registration.name!r} != {generated_name!r})"
            )
        return generator

    def _create_from_registration(
        self, *, registration: str, context: OutputGeneratorRegistryContext
    ) -> OutputGenerator:
        if registration.startswith(_OUTPUT_REGISTRATION_PREFIX):
            builtin_name = registration.removeprefix(_OUTPUT_REGISTRATION_PREFIX)
            factory = self._builtin_factories.get(builtin_name)
            if factory is None:
                raise ValueError(f"Unknown builtin output generator registration: {registration!r}")
            return factory(context)

        module_name, separator, attribute_name = registration.partition(":")
        if not separator or not module_name or not attribute_name:
            raise ValueError(
                "Output generator registration must be '<module>:<symbol>' or " "'builtin:<name>'"
            )
        module = import_module(module_name)
        candidate = getattr(module, attribute_name)

        if hasattr(candidate, "generate") and not callable(candidate):
            return _validate_output_generator(candidate)

        if callable(candidate):
            try:
                created = candidate(context)
            except TypeError:
                created = candidate()
            return _validate_output_generator(created)

        raise TypeError(
            f"Output generator registration {registration!r} resolved to unsupported object"
        )


def _validate_output_generator(candidate: object) -> OutputGenerator:
    if not hasattr(candidate, "generate"):
        raise TypeError(
            "Configured output generator does not define a generate(context=...) method"
        )
    return candidate  # type: ignore[return-value]
