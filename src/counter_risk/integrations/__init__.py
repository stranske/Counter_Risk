"""External integration modules for Counter Risk."""

from .powerpoint_com import (
    MANUAL_LINK_REFRESH_FILENAME,
    PowerPointComError,
    PowerPointComInitializationError,
    PowerPointComUnavailableError,
    initialize_powerpoint_application,
    is_powerpoint_com_available,
    list_external_link_targets,
    refresh_links_and_save,
)

__all__ = [
    "MANUAL_LINK_REFRESH_FILENAME",
    "PowerPointComError",
    "PowerPointComInitializationError",
    "PowerPointComUnavailableError",
    "initialize_powerpoint_application",
    "list_external_link_targets",
    "refresh_links_and_save",
    "is_powerpoint_com_available",
]
