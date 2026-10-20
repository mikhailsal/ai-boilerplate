"""Argument parsing and dispatch for the `quality` command."""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Callable, Sequence
from typing import cast

from quality import __version__
from quality.cli import explain_cmd, inventory_cmd, policy_cmd
from quality.diagnostics import ExitCode

type Handler = Callable[[argparse.Namespace], int]

DESCRIPTION = """\
Quality gate for Git repositories. The command-line interface decides pass or
fail; Git hooks and CI only call it. Exit codes: 0 pass, 1 violations,
2 usage or policy error, 3 environment or tool error, 4 internal error.
"""


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level parser with every implemented subcommand."""
    parser = argparse.ArgumentParser(
        prog="quality",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"quality {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>", required=True)
    explain_cmd.register(commands)
    inventory_cmd.register(commands)
    policy_cmd.register(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a deterministic exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = cast(Handler, args.handler)
    try:
        return int(handler(args))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except Exception:  # noqa: BLE001 - reported as an internal error, never as success
        traceback.print_exc(file=sys.stderr)
        print("quality: internal error (exit 4); please report it", file=sys.stderr)
        return int(ExitCode.INTERNAL)
