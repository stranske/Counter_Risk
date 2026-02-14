"""Helpers for resolving data files in source and frozen runtime modes."""

from __future__ import annotations

import os
import sys
from pathlib import Path


class RuntimePathResolutionError(FileNotFoundError):
    """Raised when a bundled runtime asset cannot be resolved."""


def _frozen_bundle_roots() -> list[Path]:
    roots: list[Path] = []

    env_root = os.environ.get("COUNTER_RISK_BUNDLE_ROOT")
    if env_root:
        roots.append(Path(env_root))

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))

    executable = getattr(sys, "executable", None)
    if executable:
        roots.append(Path(executable).resolve().parent)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(resolved)
    return deduped


def resolve_runtime_path(path: str | Path) -> Path:
    """Resolve a relative data-file path for source and bundled execution."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    if not getattr(sys, "frozen", False):
        return candidate

    roots = _frozen_bundle_roots()
    if not roots:
        raise RuntimePathResolutionError(
            f"Unable to resolve runtime asset '{candidate}'. "
            "No bundle roots were discovered from COUNTER_RISK_BUNDLE_ROOT, "
            "sys._MEIPASS, or sys.executable."
        )

    attempted_paths = [root / candidate for root in roots]
    for resolved in attempted_paths:
        if resolved.exists():
            return resolved

    searched_roots = ", ".join(str(root) for root in roots)
    searched_locations = ", ".join(str(path) for path in attempted_paths) or "<none>"
    raise RuntimePathResolutionError(
        f"Unable to resolve runtime asset '{candidate}'. "
        f"Searched roots: {searched_roots}. "
        f"Searched locations: {searched_locations}"
    )
