"""Backward-compatible entrypoint for tool version pin synchronisation."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from scripts import sync_dev_dependencies


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    # Delegate to the repo-specific sync implementation to preserve local rules.
    return sync_dev_dependencies.main(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
