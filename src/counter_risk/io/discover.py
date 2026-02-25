"""Input discovery helpers for locating monthly workflow artifacts from known roots."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from counter_risk.config import InputDiscoveryConfig, WorkflowConfig

_AS_OF_TOKEN_PATTERN = re.compile(r"\{as_of_date(?::([^}]+))?\}")


@dataclass(frozen=True, slots=True)
class DiscoveryMatch:
    """A single discovered candidate for a configured input name."""

    input_name: str
    path: Path
    root_name: str
    pattern: str


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Discovery output keyed by input name with candidate file matches."""

    matches_by_input: dict[str, tuple[DiscoveryMatch, ...]]


DEFAULT_DISCOVERABLE_INPUTS: tuple[str, ...] = (
    "raw_nisa_all_programs_xlsx",
    "mosers_all_programs_xlsx",
    "mosers_ex_trend_xlsx",
    "mosers_trend_xlsx",
    "daily_holdings_pdf",
    "hist_all_programs_3yr_xlsx",
    "hist_ex_llc_3yr_xlsx",
    "hist_llc_3yr_xlsx",
    "monthly_pptx",
)


def discover_workflow_inputs(config: WorkflowConfig, *, as_of_date: date) -> DiscoveryResult:
    """Discover workflow input candidates using configured roots and naming patterns."""

    return discover_input_candidates(
        config.input_discovery,
        as_of_date=as_of_date,
        input_names=DEFAULT_DISCOVERABLE_INPUTS,
    )


def discover_input_candidates(
    discovery_config: InputDiscoveryConfig,
    *,
    as_of_date: date,
    input_names: Iterable[str] | None = None,
) -> DiscoveryResult:
    """Discover files for the configured input names and return all candidates per input."""

    selected_inputs = tuple(input_names or tuple(discovery_config.naming_patterns))
    matches_by_input: dict[str, tuple[DiscoveryMatch, ...]] = {}

    for input_name in selected_inputs:
        patterns = tuple(discovery_config.naming_patterns.get(input_name, ()))
        if not patterns:
            matches_by_input[input_name] = ()
            continue

        root_candidates = _root_keys_for_input(input_name, discovery_config)
        discovered: list[DiscoveryMatch] = []

        for root_name in root_candidates:
            root = discovery_config.directory_roots.get(root_name)
            if root is None:
                continue

            for raw_pattern in patterns:
                resolved_pattern = _render_pattern(raw_pattern, as_of_date)
                for candidate in sorted(root.glob(resolved_pattern)):
                    if not _meets_minimum_quality(input_name, candidate):
                        continue
                    discovered.append(
                        DiscoveryMatch(
                            input_name=input_name,
                            path=candidate,
                            root_name=root_name,
                            pattern=raw_pattern,
                        )
                    )

        matches_by_input[input_name] = tuple(
            sorted(discovered, key=lambda item: str(item.path).lower())
        )

    return DiscoveryResult(matches_by_input=matches_by_input)


def discover_raw_nisa_monthly_files(
    discovery_config: InputDiscoveryConfig,
    *,
    as_of_date: date,
) -> tuple[DiscoveryMatch, ...]:
    """Discover raw NISA monthly input files."""

    return discover_input_candidates(
        discovery_config,
        as_of_date=as_of_date,
        input_names=("raw_nisa_all_programs_xlsx",),
    ).matches_by_input["raw_nisa_all_programs_xlsx"]


def discover_exposure_summary_files(
    discovery_config: InputDiscoveryConfig,
    *,
    as_of_date: date,
) -> dict[str, tuple[DiscoveryMatch, ...]]:
    """Discover MOSERS exposure summary files used by the workflow."""

    input_names = (
        "mosers_all_programs_xlsx",
        "mosers_ex_trend_xlsx",
        "mosers_trend_xlsx",
    )
    return discover_input_candidates(
        discovery_config,
        as_of_date=as_of_date,
        input_names=input_names,
    ).matches_by_input


def discover_daily_holdings_pdf_files(
    discovery_config: InputDiscoveryConfig,
    *,
    as_of_date: date,
) -> tuple[DiscoveryMatch, ...]:
    """Discover daily holdings PDF candidates for the reporting month."""

    return discover_input_candidates(
        discovery_config,
        as_of_date=as_of_date,
        input_names=("daily_holdings_pdf",),
    ).matches_by_input["daily_holdings_pdf"]


def discover_templates_and_historical_files(
    discovery_config: InputDiscoveryConfig,
    *,
    as_of_date: date,
) -> dict[str, tuple[DiscoveryMatch, ...]]:
    """Discover templates and historical workbook inputs."""

    input_names = (
        "monthly_pptx",
        "hist_all_programs_3yr_xlsx",
        "hist_ex_llc_3yr_xlsx",
        "hist_llc_3yr_xlsx",
    )
    return discover_input_candidates(
        discovery_config,
        as_of_date=as_of_date,
        input_names=input_names,
    ).matches_by_input


def _root_keys_for_input(
    input_name: str,
    discovery_config: InputDiscoveryConfig,
) -> tuple[str, ...]:
    if input_name.startswith("raw_nisa"):
        return _available_roots(discovery_config, "monthly_inputs")
    if input_name.startswith("mosers") or "exposure" in input_name:
        return _available_roots(discovery_config, "monthly_inputs", "historical_inputs")
    if input_name.endswith("_pdf") or "daily_holdings" in input_name:
        return _available_roots(
            discovery_config,
            "daily_holdings_inputs",
            "monthly_inputs",
            "historical_inputs",
        )
    if input_name.startswith("hist_"):
        return _available_roots(discovery_config, "historical_inputs", "template_inputs")
    if "template" in input_name or input_name.endswith("_pptx"):
        return _available_roots(discovery_config, "template_inputs", "historical_inputs")

    return tuple(discovery_config.directory_roots)


def _available_roots(discovery_config: InputDiscoveryConfig, *root_names: str) -> tuple[str, ...]:
    available = [name for name in root_names if name in discovery_config.directory_roots]
    if available:
        return tuple(available)
    return tuple(discovery_config.directory_roots)


def _render_pattern(pattern: str, as_of_date: date) -> str:
    def replace_token(match: re.Match[str]) -> str:
        fmt = match.group(1)
        if fmt:
            return as_of_date.strftime(fmt)
        return as_of_date.isoformat()

    return _AS_OF_TOKEN_PATTERN.sub(replace_token, pattern)


def _meets_minimum_quality(input_name: str, candidate: Path) -> bool:
    if not candidate.is_file():
        return False

    suffix = candidate.suffix.lower()
    if input_name.endswith("_pdf") or "daily_holdings" in input_name:
        return suffix == ".pdf"
    if input_name.endswith("_pptx"):
        return suffix == ".pptx"
    if input_name.endswith("_xlsx"):
        return suffix in {".xlsx", ".xlsm"}
    return True


# --- Selection helpers for resolving multiple matches ---

# Inputs that are optional in WorkflowConfig (None allowed).
_OPTIONAL_INPUTS: frozenset[str] = frozenset(
    {"raw_nisa_all_programs_xlsx", "mosers_all_programs_xlsx", "daily_holdings_pdf"}
)


def _prompt_user_selection_stdin(
    input_name: str,
    matches: tuple[DiscoveryMatch, ...],
) -> DiscoveryMatch:
    """Prompt the user on stdin to choose one match from several candidates."""

    print(f"\nMultiple matches found for '{input_name}':")
    for idx, match in enumerate(matches, start=1):
        print(f"  [{idx}] {match.path}")
    while True:
        try:
            raw = input(f"Select file for '{input_name}' (1-{len(matches)}): ")
        except (EOFError, KeyboardInterrupt) as exc:
            raise SystemExit(1) from exc
        try:
            choice = int(raw.strip())
        except ValueError:
            print(f"  Please enter a number between 1 and {len(matches)}.")
            continue
        if 1 <= choice <= len(matches):
            return matches[choice - 1]
        print(f"  Please enter a number between 1 and {len(matches)}.")


SelectionPromptFn = Callable[[str, tuple[DiscoveryMatch, ...]], DiscoveryMatch]


def resolve_discovery_selections(
    result: DiscoveryResult,
    *,
    prompt_fn: SelectionPromptFn | None = None,
) -> dict[str, Path]:
    """Resolve discovery results to at most one path per input.

    - 1 match  → auto-selected
    - N matches → delegated to *prompt_fn* (defaults to stdin prompt)
    - 0 matches → omitted from output (caller decides if that is an error)
    """

    if prompt_fn is None:
        prompt_fn = _prompt_user_selection_stdin

    selected: dict[str, Path] = {}
    for input_name, matches in result.matches_by_input.items():
        if len(matches) == 1:
            selected[input_name] = matches[0].path
        elif len(matches) > 1:
            chosen = prompt_fn(input_name, matches)
            selected[input_name] = chosen.path
    return selected
