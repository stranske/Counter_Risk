from __future__ import annotations

import logging
import sys
import types
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest

from counter_risk.pipeline.run import (
    _ole_safe_resave_historical_workbooks,
    _refresh_ppt_links,
)


class _State:
    def __init__(self) -> None:
        self.closed = False
        self.quit_called = False


def _raise_runtime_error(message: str) -> None:
    raise RuntimeError(message)


def _raise_assertion_error(message: str) -> None:
    raise AssertionError(message)


def _install_fake_win32com(monkeypatch: pytest.MonkeyPatch, app: types.SimpleNamespace) -> None:
    fake_client = types.ModuleType("win32com.client")
    cast(Any, fake_client).DispatchEx = lambda prog_id: (
        app
        if prog_id == "Excel.Application"
        else _raise_assertion_error(f"Unexpected COM application: {prog_id}")
    )
    fake_win32com = types.ModuleType("win32com")
    cast(Any, fake_win32com).client = fake_client

    monkeypatch.setitem(sys.modules, "win32com", fake_win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_client)


def test_ole_safe_resave_ignores_stale_temps_and_replaces_each_workbook(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_payloads = {
        tmp_path / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx": b"all",
        tmp_path / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx": b"llc",
    }
    for source, payload in source_payloads.items():
        source.write_bytes(payload)

    matching_stale_temp = next(iter(source_payloads)).with_suffix(".olesafe.xlsx")
    matching_stale_temp.write_bytes(b"stale")
    unrelated_stale_temp = tmp_path / "orphan.olesafe.xlsx"
    unrelated_stale_temp.write_bytes(b"orphan")

    opened: list[Path] = []
    closed: list[tuple[Path, bool]] = []
    state = _State()

    class _Workbook:
        def __init__(self, source: Path) -> None:
            self.source = source

        def SaveAs(self, destination: str, **kwargs: Any) -> None:  # noqa: N802
            assert kwargs == {"FileFormat": 51}
            Path(destination).write_bytes(b"ole-safe:" + self.source.read_bytes())

        def Close(self, save_changes: bool) -> None:  # noqa: N802
            closed.append((self.source, save_changes))

    def _open(path: str) -> _Workbook:
        source = Path(path)
        opened.append(source)
        return _Workbook(source)

    app = types.SimpleNamespace(
        DisplayAlerts=True,
        Visible=True,
        Workbooks=types.SimpleNamespace(Open=_open),
        Quit=lambda: setattr(state, "quit_called", True),
    )
    _install_fake_win32com(monkeypatch, app)

    resaved = _ole_safe_resave_historical_workbooks(tmp_path)

    expected_sources = sorted(source_payloads)
    assert resaved == expected_sources
    assert opened == expected_sources
    assert closed == [(source, False) for source in expected_sources]
    assert app.DisplayAlerts is False
    assert app.Visible is False
    assert state.quit_called is True
    for source, payload in source_payloads.items():
        assert source.read_bytes() == b"ole-safe:" + payload
    assert list(tmp_path.glob("*.olesafe.xlsx")) == []


def test_ole_safe_resave_cleans_partial_output_and_continues_after_save_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    failing_source = tmp_path / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    successful_source = tmp_path / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx"
    failing_source.write_bytes(b"keep-original")
    successful_source.write_bytes(b"replace-original")
    stuck_temp = tmp_path / "stuck.olesafe.xlsx"
    stuck_temp.write_bytes(b"locked")
    state = _State()
    sleep_calls: list[float] = []

    real_unlink = Path.unlink

    def _unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == stuck_temp:
            raise OSError("still locked")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _unlink)
    monkeypatch.setattr("time.sleep", sleep_calls.append)

    class _Workbook:
        def __init__(self, source: Path) -> None:
            self.source = source

        def SaveAs(self, destination: str, **kwargs: Any) -> None:  # noqa: N802
            assert kwargs == {"FileFormat": 51}
            output = Path(destination)
            output.write_bytes(b"partial")
            if self.source == failing_source:
                raise RuntimeError("save blocked")
            output.write_bytes(b"ole-safe:" + self.source.read_bytes())

        def Close(self, _save_changes: bool) -> None:  # noqa: N802
            return None

    app = types.SimpleNamespace(
        DisplayAlerts=True,
        Visible=True,
        Workbooks=types.SimpleNamespace(Open=lambda path: _Workbook(Path(path))),
        Quit=lambda: setattr(state, "quit_called", True),
    )
    _install_fake_win32com(monkeypatch, app)

    with caplog.at_level(logging.WARNING):
        resaved = _ole_safe_resave_historical_workbooks(tmp_path)

    assert resaved == [successful_source]
    assert failing_source.read_bytes() == b"keep-original"
    assert successful_source.read_bytes() == b"ole-safe:replace-original"
    assert list(tmp_path.glob("*.olesafe.xlsx")) == [stuck_temp]
    assert sleep_calls == [1.0] * 12
    assert state.quit_called is True
    assert f"ole_safe_resave_failed file={failing_source}" in caplog.text
    assert "save blocked" in caplog.text
    assert f"ole_safe_temp_not_removed file={stuck_temp}" in caplog.text


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
