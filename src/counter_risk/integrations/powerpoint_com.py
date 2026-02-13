"""Windows COM helpers for PowerPoint link refresh automation."""

from __future__ import annotations

import importlib.util
import sys
from contextlib import suppress
from typing import Any


class PowerPointComError(RuntimeError):
    """Base error for PowerPoint COM integration failures."""


class PowerPointComUnavailableError(PowerPointComError):
    """Raised when PowerPoint COM support is not available."""


class PowerPointComInitializationError(PowerPointComError):
    """Raised when a PowerPoint COM application instance cannot be started."""


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
    "PowerPointComError",
    "PowerPointComUnavailableError",
    "PowerPointComInitializationError",
    "initialize_powerpoint_application",
    "is_powerpoint_com_available",
]
