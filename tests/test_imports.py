"""Import smoke tests for the counter_risk package."""

from __future__ import annotations

import importlib


def test_import_counter_risk() -> None:
    module = importlib.import_module("counter_risk")
    assert hasattr(module, "__version__")


def test_import_counter_risk_logging() -> None:
    module = importlib.import_module("counter_risk.logging")
    assert hasattr(module, "configure_logging")


def test_import_counter_risk_cli() -> None:
    module = importlib.import_module("counter_risk.cli")
    assert hasattr(module, "main")
