#!/usr/bin/env python3
"""Backward-compatible entrypoint for tool version pin synchronisation."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

# Ensure the repository root is importable when this file is executed directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import sync_dev_dependencies


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    # Delegate to the repo-specific sync implementation to preserve local rules.
    return sync_dev_dependencies.main(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
