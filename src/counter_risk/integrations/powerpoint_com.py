"""Windows COM helpers for PowerPoint link refresh automation."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any


class PowerPointComError(RuntimeError):
    """Base error for PowerPoint COM integration failures."""


class PowerPointComUnavailableError(PowerPointComError):
    """Raised when PowerPoint COM support is not available."""


class PowerPointComInitializationError(PowerPointComError):
    """Raised when a PowerPoint COM application instance cannot be started."""


MANUAL_LINK_REFRESH_FILENAME = "NEEDS_LINK_REFRESH.txt"


def _as_path(path: str | Path, *, field_name: str) -> Path:
    resolved = Path(path)
    if not str(resolved):
        raise ValueError(f"{field_name} must not be empty.")
    return resolved


def _default_output_path(source_path: Path) -> Path:
    return source_path.with_name(f"{source_path.stem}_links_refreshed{source_path.suffix}")


def _extract_link_sources(link_owner: Any) -> list[str]:
    with suppress(Exception):
        raw_sources = link_owner.LinkSources()
        if raw_sources is None:
            return []
        if isinstance(raw_sources, str):
            return [raw_sources]
        try:
            return [str(item) for item in raw_sources if item]
        except TypeError:
            return [str(raw_sources)]
    return []


def _write_manual_refresh_instructions(
    *,
    run_folder: Path,
    source_pptx_path: Path,
    output_pptx_path: Path,
    reason: str,
) -> Path:
    run_folder.mkdir(parents=True, exist_ok=True)
    instructions_path = run_folder / MANUAL_LINK_REFRESH_FILENAME
    instructions_path.write_text(
        "\n".join(
            [
                "PowerPoint links were not refreshed automatically.",
                "",
                f"Reason: {reason}",
                f"Input presentation: {source_pptx_path}",
                f"Output presentation: {output_pptx_path}",
                "",
                "Manual refresh steps:",
                "1. Open the output presentation in Microsoft PowerPoint.",
                "2. Go to File -> Info -> Edit Links to File.",
                "3. In the Links dialog, click 'Select All'.",
                "4. Click 'Update Now'.",
                "5. Confirm every linked item shows an updated status/path.",
                "6. Save the presentation and close PowerPoint.",
                "",
                "Do not distribute this deck until link refresh succeeds.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return instructions_path


def _load_dispatch_ex() -> Any:
    """Load and return the ``DispatchEx`` COM constructor for PowerPoint automation."""

    if sys.platform != "win32":
        raise PowerPointComUnavailableError(
            "PowerPoint COM automation is only available on Windows (sys.platform == 'win32')."
        )

    if importlib.util.find_spec("win32com.client") is None:
        raise PowerPointComUnavailableError(
            "Missing win32com.client; install pywin32 on a Windows host with Office installed."
        )

    try:
        from win32com.client import DispatchEx
    except Exception as exc:
        raise PowerPointComUnavailableError(
            "win32com.client is present but failed to import cleanly."
        ) from exc

    return DispatchEx


def initialize_powerpoint_application() -> Any:
    """Initialize and return a PowerPoint COM application object.

    Raises:
        PowerPointComUnavailableError: COM prerequisites are missing.
        PowerPointComInitializationError: PowerPoint COM failed to launch.
    """

    dispatch_ex = _load_dispatch_ex()

    try:
        app = dispatch_ex("PowerPoint.Application")
    except Exception as exc:
        raise PowerPointComInitializationError(
            "Failed to initialize PowerPoint COM via DispatchEx('PowerPoint.Application')."
        ) from exc

    return app


def list_external_link_targets(pptx_path: str | Path) -> list[str]:
    """List external link targets found in a PowerPoint presentation.

    Raises:
        FileNotFoundError: The input file does not exist.
        PowerPointComError: COM initialization/open errors.
    """

    source_path = _as_path(pptx_path, field_name="pptx_path")
    if not source_path.exists():
        raise FileNotFoundError(f"Presentation not found: {source_path}")

    app = initialize_powerpoint_application()
    presentation: Any | None = None
    targets: list[str] = []
    try:
        with suppress(Exception):
            app.Visible = 0  # Headless/background mode where supported.
        presentation = app.Presentations.Open(str(source_path), False, True, False)
        targets.extend(_extract_link_sources(presentation))

        for slide in presentation.Slides:
            for shape in slide.Shapes:
                with suppress(Exception):
                    link_target = str(shape.LinkFormat.SourceFullName)
                    if link_target:
                        targets.append(link_target)
    finally:
        if presentation is not None:
            with suppress(Exception):
                presentation.Close()
        with suppress(Exception):
            app.Quit()

    return list(dict.fromkeys(targets))


def refresh_links_and_save(pptx_path: str | Path, output_pptx_path: str | Path | None = None) -> Path:
    """Refresh external links using PowerPoint COM and save to a new file.

    If COM is unavailable, this function copies the presentation to the output path,
    writes ``NEEDS_LINK_REFRESH.txt`` beside the output, and returns the output path.

    Raises:
        FileNotFoundError: The input file does not exist.
        PowerPointComInitializationError: COM exists but PowerPoint failed to initialize.
    """

    source_path = _as_path(pptx_path, field_name="pptx_path")
    if not source_path.exists():
        raise FileNotFoundError(f"Presentation not found: {source_path}")

    output_path = (
        _as_path(output_pptx_path, field_name="output_pptx_path")
        if output_pptx_path is not None
        else _default_output_path(source_path)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        app = initialize_powerpoint_application()
    except PowerPointComUnavailableError as exc:
        if source_path.resolve() != output_path.resolve():
            shutil.copy2(source_path, output_path)
        _write_manual_refresh_instructions(
            run_folder=output_path.parent,
            source_pptx_path=source_path,
            output_pptx_path=output_path,
            reason=str(exc),
        )
        return output_path

    presentation: Any | None = None
    try:
        with suppress(Exception):
            app.Visible = 0  # Headless/background mode where supported.
        presentation = app.Presentations.Open(str(source_path), False, False, False)

        with suppress(Exception):
            presentation.UpdateLinks()

        for slide in presentation.Slides:
            for shape in slide.Shapes:
                with suppress(Exception):
                    shape.LinkFormat.Update()

        presentation.SaveCopyAs(str(output_path))
    finally:
        if presentation is not None:
            with suppress(Exception):
                presentation.Close()
        with suppress(Exception):
            app.Quit()

    return output_path


def is_powerpoint_com_available() -> bool:
    """Return ``True`` if PowerPoint COM appears callable on this host."""

    try:
        app = initialize_powerpoint_application()
    except PowerPointComError:
        return False

    # COM servers can already be in the process of teardown; availability check still passed.
    with suppress(Exception):
        app.Quit()

    return True


__all__ = [
    "MANUAL_LINK_REFRESH_FILENAME",
    "PowerPointComError",
    "PowerPointComUnavailableError",
    "PowerPointComInitializationError",
    "initialize_powerpoint_application",
    "list_external_link_targets",
    "refresh_links_and_save",
    "is_powerpoint_com_available",
]
