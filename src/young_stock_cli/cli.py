"""CLI entry point for `young` command.

Thin wrapper around :mod:`young_stock_cli._core.main` that translates the
modern `young <market> [date]` subcommand syntax into the legacy
`--market <m> [date]` argv that ``_core.main`` understands.
"""
from __future__ import annotations

import sys
from typing import List, Optional

from . import __version__
from ._core import main as _core_main

USAGE = """\
young-stock-cli v{version}

Usage:
  young a   [YYYYMMDD] [--no-cache]   A-share post-market replay
  young hk  [YYYYMMDD] [--no-cache]   Hong Kong post-market replay
  young us  [YYYYMMDD] [--no-cache]   US post-market replay
  young global [YYYYMMDD] [--no-cache]  Global indices snapshot

  young --version                     Show version
  young --help                        Show this help

Examples:
  young a                # latest trading day, A-share
  young a 20260526       # specific date
  young global           # US + HK + A-share indices
""".format(version=__version__)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0
    if argv[0] in {"-V", "--version", "version"}:
        print(f"young-stock-cli {__version__}")
        return 0

    market = argv[0]
    if market not in {"a", "hk", "us", "global"}:
        print(f"Unknown command: {market}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    # Translate to legacy argv consumed by _core.main()
    forwarded = ["--market", market] + argv[1:]
    sys.argv = ["young"] + forwarded
    try:
        _core_main()
    except SystemExit as exc:
        return int(exc.code or 0)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
