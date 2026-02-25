from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.integrations import powerpoint_com


def test_refresh_links_cleanup_failures_are_logged_not_silently_suppressed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    class _FakePresentation:
        Slides: list[object] = []

        def UpdateLinks(self) -> None:  # noqa: N802
            return None

        def SaveCopyAs(self, path: str) -> None:  # noqa: N802
            Path(path).write_bytes(b"pptx")

        def Close(self) -> None:  # noqa: N802
            raise RuntimeError("close failed")

    class _FakePresentations:
        def __init__(self, presentation: _FakePresentation) -> None:
            self._presentation = presentation

        def Open(  # noqa: N802
            self, _path: str, _with_window: bool, _read_only: bool, _untitled: bool
        ) -> _FakePresentation:
            return self._presentation

    class _FakeApp:
        def __init__(self, presentation: _FakePresentation) -> None:
            self.Presentations = _FakePresentations(presentation)
            self.Visible = 0

        def Quit(self) -> None:  # noqa: N802
            raise ValueError("quit failed")

    source_pptx = tmp_path / "input.pptx"
    output_pptx = tmp_path / "output.pptx"
    source_pptx.write_bytes(b"pptx")
    monkeypatch.setattr(
        powerpoint_com,
        "initialize_powerpoint_application",
        lambda: _FakeApp(_FakePresentation()),
    )

    caplog.set_level("ERROR", logger="counter_risk.integrations.powerpoint_com")
    returned = powerpoint_com.refresh_links_and_save(source_pptx, output_pptx)

    assert returned == output_pptx
    assert output_pptx.exists()
    assert "action=presentation.Close exc_type=RuntimeError exc=close failed" in caplog.text
    assert "action=app.Quit exc_type=ValueError exc=quit failed" in caplog.text


def test_refresh_links_cleanup_failure_reraises_when_env_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _FakePresentation:
        def UpdateLinks(self) -> None:  # noqa: N802
            return None

        def SaveCopyAs(self, _path: str) -> None:  # noqa: N802
            return None

        def Close(self) -> None:  # noqa: N802
            raise RuntimeError("close failed")

    class _FakePresentations:
        def __init__(self, presentation: _FakePresentation) -> None:
            self._presentation = presentation

        def Open(  # noqa: N802
            self, _path: str, _with_window: bool, _read_only: bool, _untitled: bool
        ) -> _FakePresentation:
            return self._presentation

    class _FakeApp:
        def __init__(self, presentation: _FakePresentation) -> None:
            self.Presentations = _FakePresentations(presentation)
            self.Visible = 0

        def Quit(self) -> None:  # noqa: N802
            return None

    source_pptx = tmp_path / "input.pptx"
    output_pptx = tmp_path / "output.pptx"
    source_pptx.write_bytes(b"pptx")
    monkeypatch.setenv("COUNTER_RISK_RERAISE_COM_CLEANUP_ERRORS", "true")
    monkeypatch.setattr(
        powerpoint_com,
        "initialize_powerpoint_application",
        lambda: _FakeApp(_FakePresentation()),
    )

    with pytest.raises(RuntimeError, match="close failed"):
        powerpoint_com.refresh_links_and_save(source_pptx, output_pptx)


def test_is_powerpoint_com_available_logs_quit_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class _FakeApp:
        def Quit(self) -> None:  # noqa: N802
            raise RuntimeError("quit failed")

    monkeypatch.setattr(powerpoint_com, "initialize_powerpoint_application", lambda: _FakeApp())
    caplog.set_level("ERROR", logger="counter_risk.integrations.powerpoint_com")

    assert powerpoint_com.is_powerpoint_com_available() is True
    assert "action=app.Quit exc_type=RuntimeError exc=quit failed" in caplog.text
