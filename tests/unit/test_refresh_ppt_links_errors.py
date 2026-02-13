from __future__ import annotations

import logging
import sys
import types
from pathlib import Path

import pytest

from counter_risk.pipeline.run import _refresh_ppt_links


class _State:
    def __init__(self) -> None:
        self.closed = False
        self.quit_called = False


def _raise_runtime_error(message: str) -> None:
    raise RuntimeError(message)


def _raise_assertion_error(message: str) -> None:
    raise AssertionError(message)


def test_refresh_ppt_links_surfaces_com_failures_with_context(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    monkeypatch.setattr("counter_risk.pipeline.run.platform.system", lambda: "Windows")
    state = _State()

    presentation = types.SimpleNamespace()
    presentation.UpdateLinks = lambda: _raise_runtime_error("COM update failed")
    presentation.Save = lambda: _raise_assertion_error(
        "Save should not be called after UpdateLinks failure"
    )
    presentation.Close = lambda: setattr(state, "closed", True)

    presentations = types.SimpleNamespace()
    presentations.Open = (
        lambda _path, **kwargs: _raise_assertion_error("WithWindow was not passed")
        if "WithWindow" not in kwargs
        else presentation
    )

    app = types.SimpleNamespace()
    app.Visible = True
    app.Presentations = presentations
    app.Quit = lambda: setattr(state, "quit_called", True)

    fake_client = types.ModuleType("win32com.client")
    fake_client.DispatchEx = lambda _prog_id: app
    fake_win32com = types.ModuleType("win32com")
    fake_win32com.client = fake_client

    monkeypatch.setitem(sys.modules, "win32com", fake_win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_client)

    ppt_path = tmp_path / "monthly.pptx"
    ppt_path.write_bytes(b"ppt")

    with caplog.at_level(logging.ERROR), pytest.raises(
        RuntimeError, match="PPT link refresh failed"
    ) as exc_info:
        _refresh_ppt_links(ppt_path)

    assert str(ppt_path) in str(exc_info.value)
    assert "COM update failed" in str(exc_info.value)
    assert state.closed is True
    assert state.quit_called is True
    assert "ppt_link_refresh_failed file=" in caplog.text
