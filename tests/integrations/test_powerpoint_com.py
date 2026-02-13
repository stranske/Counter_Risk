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
        lambda: (_ for _ in ()).throw(
            powerpoint_com.PowerPointComUnavailableError("COM unavailable")
        ),
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
        lambda: (_ for _ in ()).throw(
            powerpoint_com.PowerPointComUnavailableError("not on windows")
        ),
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


def test_refresh_links_and_save_updates_links_and_saves_when_com_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeLinkFormat:
        def __init__(self, source: str | None = None) -> None:
            self.source = source or ""
            self.update_calls = 0

        @property
        def SourceFullName(self) -> str:  # noqa: N802
            return self.source

        def Update(self) -> None:  # noqa: N802
            self.update_calls += 1

    class FakeShape:
        def __init__(
            self,
            link_format: FakeLinkFormat | None = None,
            group_items: list["FakeShape"] | None = None,
        ) -> None:
            self.LinkFormat = link_format or FakeLinkFormat()
            self.GroupItems = group_items or []

    class FakeSlide:
        def __init__(self, shapes: list[FakeShape]) -> None:
            self.Shapes = shapes

    class FakePresentation:
        def __init__(self) -> None:
            self.update_links_calls = 0
            self.save_copy_paths: list[str] = []
            self.close_calls = 0
            grouped_shape = FakeShape(
                FakeLinkFormat(),
                [FakeShape(FakeLinkFormat()), FakeShape(FakeLinkFormat())],
            )
            self.Slides = [
                FakeSlide([grouped_shape, FakeShape(FakeLinkFormat())]),
                FakeSlide([FakeShape(FakeLinkFormat())]),
            ]

        def UpdateLinks(self) -> None:  # noqa: N802
            self.update_links_calls += 1

        def SaveCopyAs(self, path: str) -> None:  # noqa: N802
            self.save_copy_paths.append(path)

        def Close(self) -> None:  # noqa: N802
            self.close_calls += 1

    class FakePresentations:
        def __init__(self, presentation: FakePresentation) -> None:
            self.presentation = presentation
            self.open_args: list[tuple[str, bool, bool, bool]] = []

        def Open(  # noqa: N802
            self, path: str, with_window: bool, read_only: bool, untitled: bool
        ) -> FakePresentation:
            self.open_args.append((path, with_window, read_only, untitled))
            return self.presentation

    class FakeApp:
        def __init__(self, presentation: FakePresentation) -> None:
            self.Presentations = FakePresentations(presentation)
            self.Visible: int | None = None
            self.quit_calls = 0

        def Quit(self) -> None:  # noqa: N802
            self.quit_calls += 1

    source_pptx = tmp_path / "in.pptx"
    output_pptx = tmp_path / "out.pptx"
    source_pptx.write_bytes(b"stub")

    presentation = FakePresentation()
    app = FakeApp(presentation)
    monkeypatch.setattr(powerpoint_com, "initialize_powerpoint_application", lambda: app)

    returned = powerpoint_com.refresh_links_and_save(source_pptx, output_pptx)

    assert returned == output_pptx
    assert app.Visible == 0
    assert app.Presentations.open_args == [(str(source_pptx), False, False, False)]
    assert presentation.update_links_calls == 1
    assert presentation.save_copy_paths == [str(output_pptx)]
    assert presentation.close_calls == 1
    assert app.quit_calls == 1
    shape_updates = sum(
        shape.LinkFormat.update_calls for slide in presentation.Slides for shape in slide.Shapes
    )
    grouped_shape_updates = sum(
        grouped_shape.LinkFormat.update_calls
        for slide in presentation.Slides
        for shape in slide.Shapes
        for grouped_shape in shape.GroupItems
    )
    assert shape_updates + grouped_shape_updates == 5


def test_list_external_link_targets_collects_presentation_and_shape_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeLinkFormat:
        def __init__(self, source: str | None = None, *, raise_on_source: bool = False) -> None:
            self.source = source
            self.raise_on_source = raise_on_source

        @property
        def SourceFullName(self) -> str:  # noqa: N802
            if self.raise_on_source:
                raise RuntimeError("link source unavailable")
            return self.source or ""

    class FakeShape:
        def __init__(
            self,
            link_format: FakeLinkFormat,
            group_items: list["FakeShape"] | None = None,
        ) -> None:
            self.LinkFormat = link_format
            self.GroupItems = group_items or []

    class FakeSlide:
        def __init__(self, shapes: list[FakeShape]) -> None:
            self.Shapes = shapes

    class FakePresentation:
        def __init__(self) -> None:
            self.Slides = [
                FakeSlide(
                    [
                        FakeShape(FakeLinkFormat("X:\\linked\\book1.xlsx")),
                        FakeShape(
                            FakeLinkFormat(""),
                            [
                                FakeShape(FakeLinkFormat("X:\\linked\\book3.xlsx")),
                                FakeShape(FakeLinkFormat("X:\\linked\\book2.xlsx")),
                            ],
                        ),
                        FakeShape(FakeLinkFormat("X:\\linked\\book2.xlsx")),
                        FakeShape(FakeLinkFormat("X:\\linked\\book1.xlsx")),
                        FakeShape(FakeLinkFormat(raise_on_source=True)),
                    ]
                )
            ]
            self.close_calls = 0

        def LinkSources(self) -> list[str]:  # noqa: N802
            return ["X:\\linked\\book0.xlsx", "X:\\linked\\book1.xlsx"]

        def Close(self) -> None:  # noqa: N802
            self.close_calls += 1

    class FakePresentations:
        def __init__(self, presentation: FakePresentation) -> None:
            self.presentation = presentation
            self.open_args: list[tuple[str, bool, bool, bool]] = []

        def Open(  # noqa: N802
            self, path: str, with_window: bool, read_only: bool, untitled: bool
        ) -> FakePresentation:
            self.open_args.append((path, with_window, read_only, untitled))
            return self.presentation

    class FakeApp:
        def __init__(self, presentation: FakePresentation) -> None:
            self.Presentations = FakePresentations(presentation)
            self.Visible: int | None = None
            self.quit_calls = 0

        def Quit(self) -> None:  # noqa: N802
            self.quit_calls += 1

    source_pptx = tmp_path / "input.pptx"
    source_pptx.write_bytes(b"pptx")

    presentation = FakePresentation()
    app = FakeApp(presentation)
    monkeypatch.setattr(powerpoint_com, "initialize_powerpoint_application", lambda: app)

    targets = powerpoint_com.list_external_link_targets(source_pptx)

    assert targets == [
        "X:\\linked\\book0.xlsx",
        "X:\\linked\\book1.xlsx",
        "X:\\linked\\book3.xlsx",
        "X:\\linked\\book2.xlsx",
    ]
    assert app.Visible == 0
    assert app.Presentations.open_args == [(str(source_pptx), False, True, False)]
    assert presentation.close_calls == 1
    assert app.quit_calls == 1
