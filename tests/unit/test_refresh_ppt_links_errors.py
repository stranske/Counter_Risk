from __future__ import annotations

import logging
import sys
import types
import zipfile
from pathlib import Path
from typing import Any, cast

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

    # UpdateLinks failing is TOLERATED: PowerPoint raises from it even when the
    # refresh goes on to succeed, and the per-shape LinkFormat.Update calls are what
    # actually re-render the charts. A failure in a REQUIRED step -- here, walking
    # the slides -- must still surface with context and must not reach Save.
    class _FailingSlides:
        def __iter__(self):  # type: ignore[no-untyped-def]
            _raise_runtime_error("COM update failed")

    presentation = types.SimpleNamespace()
    presentation.UpdateLinks = lambda: None
    presentation.Slides = _FailingSlides()
    presentation.Save = lambda: _raise_assertion_error(
        "Save should not be called after a failed slide walk"
    )
    presentation.Close = lambda: setattr(state, "closed", True)

    presentations = types.SimpleNamespace()
    presentations.Open = lambda _path, **kwargs: (
        _raise_assertion_error("WithWindow was not passed")
        if "WithWindow" not in kwargs
        else presentation
    )

    app = types.SimpleNamespace()
    app.Visible = True
    app.Presentations = presentations
    app.Quit = lambda: setattr(state, "quit_called", True)

    fake_client = types.ModuleType("win32com.client")
    cast(Any, fake_client).DispatchEx = lambda _prog_id: app
    fake_win32com = types.ModuleType("win32com")
    cast(Any, fake_win32com).client = fake_client

    monkeypatch.setitem(sys.modules, "win32com", fake_win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_client)

    ppt_path = tmp_path / "monthly.pptx"
    # Must be a real zip: the refresh now runs a preparation step that rewrites the
    # deck's chart link targets in-place, and a repoint failure is deliberately
    # fatal (silently leaving links pointed elsewhere would render stale charts).
    # The archive contents are irrelevant here -- no chart rels means nothing to
    # repoint -- so this only has to be zip-shaped for prep to succeed and let the
    # COM failure under test surface.
    with zipfile.ZipFile(ppt_path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")

    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(RuntimeError, match="PPT link refresh failed") as exc_info,
    ):
        _refresh_ppt_links(ppt_path)

    assert str(ppt_path) in str(exc_info.value)
    assert "COM update failed" in str(exc_info.value)
    assert state.closed is True
    assert state.quit_called is True
    assert "ppt_link_refresh_failed file=" in caplog.text


class _VisibleBlockedApp:
    """Fake COM app whose ``Visible`` setter raises, like an Office security policy that
    forbids hiding the application window (observed: ``Application.Visible : Invalid
    request.  Hiding the application window is not allowed.``)."""

    def __init__(self, presentations: Any, state: _State) -> None:
        self.Presentations = presentations
        self._quit_state = state

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "Visible":
            raise RuntimeError(
                "Application.Visible : Invalid request.  Hiding the application "
                "window is not allowed."
            )
        object.__setattr__(self, name, value)

    def Quit(self) -> None:  # noqa: N802 - mirror the PowerPoint COM API
        self._quit_state.quit_called = True


def test_refresh_ppt_links_succeeds_when_visible_cannot_be_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression test: some Office security policies block `Application.Visible =
    False`, but `Presentations.Open(..., WithWindow=False)` alone is sufficient to keep
    the document window hidden, so the refresh should still complete successfully."""

    monkeypatch.setattr("counter_risk.pipeline.run.platform.system", lambda: "Windows")
    state = _State()

    presentation = types.SimpleNamespace()
    presentation.UpdateLinks = lambda: None
    presentation.Slides = []  # no shapes to walk; the refresh should still complete
    presentation.Save = lambda: None
    presentation.Close = lambda: setattr(state, "closed", True)

    presentations = types.SimpleNamespace()
    presentations.Open = lambda _path, **kwargs: (
        _raise_assertion_error("WithWindow was not passed")
        if "WithWindow" not in kwargs
        else presentation
    )

    app = _VisibleBlockedApp(presentations=presentations, state=state)

    fake_client = types.ModuleType("win32com.client")
    cast(Any, fake_client).DispatchEx = lambda _prog_id: app
    fake_win32com = types.ModuleType("win32com")
    cast(Any, fake_win32com).client = fake_client

    monkeypatch.setitem(sys.modules, "win32com", fake_win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_client)

    ppt_path = tmp_path / "monthly.pptx"
    # Must be a real zip: the refresh now runs a preparation step that rewrites the
    # deck's chart link targets in-place, and a repoint failure is deliberately
    # fatal (silently leaving links pointed elsewhere would render stale charts).
    # The archive contents are irrelevant here -- no chart rels means nothing to
    # repoint -- so this only has to be zip-shaped for prep to succeed and let the
    # COM failure under test surface.
    with zipfile.ZipFile(ppt_path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")

    from counter_risk.pipeline.run import PptProcessingStatus

    result = _refresh_ppt_links(ppt_path)

    assert result.status == PptProcessingStatus.SUCCESS
    assert state.closed is True
    assert state.quit_called is True
