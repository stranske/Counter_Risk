"""Runtime hook to expose the bundled root directory for path resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _resolve_bundle_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()
    return Path(sys.executable).resolve().parent


os.environ.setdefault("COUNTER_RISK_BUNDLE_ROOT", str(_resolve_bundle_root()))
