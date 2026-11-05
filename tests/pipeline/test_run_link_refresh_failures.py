"""Pipeline link refresh must fail safely and release Office resources."""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from counter_risk.pipeline import run as run_module


@pytest.fixture
def link_refresh_dependencies(monkeypatch):
    """Replace Office boundaries while exercising the pipeline's refresh policy."""
    monkeypatch.setattr(run_module.platform, "system", lambda: "Windows")
    dispatch = Mock()
    client = ModuleType("win32com.client")
    client.DispatchEx = dispatch
    package = ModuleType("win32com")
    package.client = client
    monkeypatch.setitem(sys.modules, "win32com", package)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    resave = Mock(return_value=[])
    repoint = Mock(return_value=(0, 0))
    monkeypatch.setattr(run_module, "_ole_safe_resave_historical_workbooks", resave)
    monkeypatch.setattr(run_module, "_repoint_and_autoscale_ppt_charts", repoint)
    return SimpleNamespace(dispatch=dispatch, resave=resave, repoint=repoint)


@pytest.mark.parametrize("stage", ["resave", "repoint"])
def test_link_preparation_failure_stops_refresh_and_preserves_cause(
    link_refresh_dependencies, tmp_path: Path, stage
) -> None:
    dependencies = link_refresh_dependencies
    path = tmp_path / "monthly.pptx"
    failure = OSError("historical link source is unreadable")
    getattr(dependencies, stage).side_effect = failure

    with pytest.raises(RuntimeError, match="PPT link prep failed") as raised:
        run_module._refresh_ppt_links(path)

    assert raised.value.__cause__ is failure
    assert str(path) in str(raised.value)
    assert str(failure) in str(raised.value)
    dependencies.resave.assert_called_once_with(tmp_path)
    if stage == "resave":
        dependencies.repoint.assert_not_called()
    else:
        dependencies.repoint.assert_called_once_with(path, tmp_path)
    dependencies.dispatch.assert_not_called()


def test_missing_office_client_skips_refresh_before_preparing_files(
    link_refresh_dependencies, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "win32com.client", None)

    result = run_module._refresh_ppt_links(tmp_path / "monthly.pptx")

    assert result.status is run_module.PptProcessingStatus.SKIPPED
    assert result.error_detail == "win32com unavailable"
    link_refresh_dependencies.resave.assert_not_called()
    link_refresh_dependencies.repoint.assert_not_called()
    link_refresh_dependencies.dispatch.assert_not_called()


def test_refresh_continues_after_unlinked_shape_and_bulk_update_failures(
    link_refresh_dependencies, tmp_path: Path
) -> None:
    failed_shape = SimpleNamespace(LinkFormat=Mock())
    failed_shape.LinkFormat.Update.side_effect = RuntimeError("shape has no link")
    linked_shape = SimpleNamespace(LinkFormat=Mock())
    presentation = Mock()
    presentation.UpdateLinks.side_effect = RuntimeError("bulk update unsupported")
    presentation.Slides = [SimpleNamespace(Shapes=[failed_shape, linked_shape])]
    app = Mock()
    app.Presentations.Open.return_value = presentation
    link_refresh_dependencies.dispatch.return_value = app
    path = tmp_path / "monthly.pptx"

    result = run_module._refresh_ppt_links(path)

    assert result.status is run_module.PptProcessingStatus.SUCCESS
    link_refresh_dependencies.dispatch.assert_called_once_with("PowerPoint.Application")
    app.Presentations.Open.assert_called_once_with(str(path), WithWindow=False)
    presentation.UpdateLinks.assert_called_once_with()
    failed_shape.LinkFormat.Update.assert_called_once_with()
    linked_shape.LinkFormat.Update.assert_called_once_with()
    presentation.Save.assert_called_once_with()
    presentation.Close.assert_called_once_with()
    app.Quit.assert_called_once_with()


def test_refresh_save_failure_preserves_cause_and_releases_office(
    link_refresh_dependencies, tmp_path: Path
) -> None:
    failure = OSError("presentation is read-only")
    presentation = Mock(Slides=[])
    presentation.Save.side_effect = failure
    app = Mock()
    app.Presentations.Open.return_value = presentation
    link_refresh_dependencies.dispatch.return_value = app
    path = tmp_path / "monthly.pptx"

    with pytest.raises(RuntimeError, match="PPT link refresh failed") as raised:
        run_module._refresh_ppt_links(path)

    assert raised.value.__cause__ is failure
    assert str(path) in str(raised.value)
    assert str(failure) in str(raised.value)
    presentation.Save.assert_called_once_with()
    presentation.Close.assert_called_once_with()
    app.Quit.assert_called_once_with()
