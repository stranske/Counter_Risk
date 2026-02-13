"""External integration modules for Counter Risk."""

from .powerpoint_com import (
    PowerPointComError,
    PowerPointComInitializationError,
    PowerPointComUnavailableError,
    initialize_powerpoint_application,
    is_powerpoint_com_available,
)

__all__ = [
    "PowerPointComError",
    "PowerPointComInitializationError",
    "PowerPointComUnavailableError",
    "initialize_powerpoint_application",
    "is_powerpoint_com_available",
]
