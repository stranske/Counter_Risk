"""Helpers for resolving data files in source and frozen runtime modes."""

from __future__ import annotations

import os
import sys
from pathlib import Path


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

    for root in _frozen_bundle_roots():
        resolved = root / candidate
        if resolved.exists():
            return resolved

    roots = _frozen_bundle_roots()
    if roots:
        return roots[0] / candidate
    return candidate
