"""Pipeline test configuration.

Automatically marks ``test_run_pipeline_*`` tests as *slow* because every one
of them calls :func:`run_pipeline` with real Excel fixture files, making each
invocation take 100-170 s on CI runners.  The PR gate excludes ``slow``-marked
tests so feedback stays under five minutes; the full suite still runs on main.
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    slow = pytest.mark.slow
    for item in items:
        if (
            item.fspath is not None
            and item.fspath.basename == "test_run_pipeline.py"
            and item.name.startswith("test_run_pipeline_")
        ):
            item.add_marker(slow)
