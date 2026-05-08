"""Global pytest collection hooks for CI-friendly test selection."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark integration directory tests as slow for PR-gate runs."""
    slow = pytest.mark.slow
    for item in items:
        item_path = getattr(item, "path", None)
        if item_path is None:
            continue
        try:
            relative_parts = Path(item_path).parts
        except TypeError:
            continue
        if "integration" in relative_parts and "tests" in relative_parts:
            item.add_marker(slow)
