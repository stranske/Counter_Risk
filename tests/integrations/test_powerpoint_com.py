"""Unit tests for PowerPoint COM availability and initialization helpers."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from counter_risk.integrations import powerpoint_com


def test_is_powerpoint_com_available_false_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(powerpoint_com.sys, "platform", "linux")

    assert powerpoint_com.is_powerpoint_com_available() is False


def test_is_powerpoint_com_available_false_when_win32com_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(powerpoint_com.sys, "platform", "win32")
    monkeypatch.setattr(powerpoint_com.importlib.util, "find_spec", lambda _: None)

    assert powerpoint_com.is_powerpoint_com_available() is False


def test_is_powerpoint_com_available_true_when_dispatch_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeApp:
        def __init__(self) -> None:
            self.quit_called = False

        def Quit(self) -> None:
            self.quit_called = True

    app = FakeApp()

    def fake_dispatch_ex(prog_id: str) -> Any:
        assert prog_id == "PowerPoint.Application"
        return app

    win32com_mod = types.ModuleType("win32com")
    client_mod = types.ModuleType("win32com.client")
    client_mod.DispatchEx = fake_dispatch_ex  # type: ignore[attr-defined]
    win32com_mod.client = client_mod  # type: ignore[attr-defined]

    monkeypatch.setattr(powerpoint_com.sys, "platform", "win32")
    monkeypatch.setattr(
        powerpoint_com.importlib.util,
        "find_spec",
        lambda name: object() if name == "win32com.client" else None,
    )
    monkeypatch.setitem(sys.modules, "win32com", win32com_mod)
    monkeypatch.setitem(sys.modules, "win32com.client", client_mod)

    assert powerpoint_com.is_powerpoint_com_available() is True
    assert app.quit_called is True


def test_initialize_powerpoint_application_raises_unavailable_on_non_windows() -> None:
    with pytest.raises(powerpoint_com.PowerPointComUnavailableError):
        powerpoint_com._load_dispatch_ex()


def test_initialize_powerpoint_application_wraps_dispatch_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def bad_dispatch_ex(_: str) -> Any:
        raise RuntimeError("com init failed")

    monkeypatch.setattr(powerpoint_com, "_load_dispatch_ex", lambda: bad_dispatch_ex)

    with pytest.raises(powerpoint_com.PowerPointComInitializationError) as exc_info:
        powerpoint_com.initialize_powerpoint_application()

    assert isinstance(exc_info.value.__cause__, RuntimeError)
