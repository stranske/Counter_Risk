"""Unit tests for PowerPoint COM availability and initialization helpers."""

from __future__ import annotations

import stat
import sys
import types
from pathlib import Path
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

        def Quit(self) -> None:  # noqa: N802
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


def test_refresh_links_and_save_writes_manual_instructions_when_com_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_pptx = tmp_path / "Monthly Counterparty Exposure Report.pptx"
    source_pptx.write_bytes(b"pptx-content")

    monkeypatch.setattr(
        powerpoint_com,
        "initialize_powerpoint_application",
        lambda: (_ for _ in ()).throw(powerpoint_com.PowerPointComUnavailableError("COM unavailable")),
    )

    output_path = powerpoint_com.refresh_links_and_save(source_pptx)

    assert output_path.exists()
    assert output_path.name.endswith("_links_refreshed.pptx")
    assert output_path.read_bytes() == b"pptx-content"

    instructions_path = output_path.parent / powerpoint_com.MANUAL_LINK_REFRESH_FILENAME
    assert instructions_path.exists()

    mode = instructions_path.stat().st_mode
    assert bool(mode & stat.S_IRUSR)
    assert bool(mode & stat.S_IWUSR)


def test_refresh_links_fallback_instructions_include_manual_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_pptx = tmp_path / "input.pptx"
    output_pptx = tmp_path / "run_2026-01-31" / "output.pptx"
    source_pptx.write_bytes(b"sample")

    monkeypatch.setattr(
        powerpoint_com,
        "initialize_powerpoint_application",
        lambda: (_ for _ in ()).throw(powerpoint_com.PowerPointComUnavailableError("not on windows")),
    )

    returned_path = powerpoint_com.refresh_links_and_save(source_pptx, output_pptx)
    assert returned_path == output_pptx

    instructions_path = output_pptx.parent / powerpoint_com.MANUAL_LINK_REFRESH_FILENAME
    content = instructions_path.read_text(encoding="utf-8")
    assert "Edit Links to File" in content
    assert "Update Now" in content
    assert "Open the output presentation in Microsoft PowerPoint." in content
    assert f"Input presentation: {source_pptx}" in content
    assert f"Output presentation: {output_pptx}" in content
