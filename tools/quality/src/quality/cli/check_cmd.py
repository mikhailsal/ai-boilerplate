"""`quality check`: every gate over the staged candidate or a revision."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from quality.catalog import build_registry
from quality.cli import Subcommands
from quality.cli.local import (
    candidate_of,
    coverage_json,
    coverage_text,
    local_profiles,
    local_tools,
)
from quality.diagnostics import Outcome
from quality.diagnostics.render import outcome_to_json, render_text
from quality.engine import Report, Settings, check_candidate
from quality.gitio import GitioError
from quality.toolchain import ToolchainError

NAME = "check"
ACTIONS: frozenset[str] = frozenset()


def register(commands: Subcommands) -> None:
    """Add the `check` subcommand."""
    parser = commands.add_parser(
        NAME,
        help="run every gate over the staged candidate or a revision",
        description="Materialize the candidate (the index by default, or --rev) in isolation "
        "and run the repository, documentation, secret, structure, and architecture gates, "
        "then the native configuration, format, lint, type, and unit test gates with coverage "
        "of the components the change affects (every active component with --all). "
        "Exit 0 on pass, 1 on violations, 2 on policy errors, 3 on environment errors.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--staged", action="store_true", help="check the Git index (default)")
    source.add_argument("--rev", help="check a commit instead of the index")
    parser.add_argument(
        "--all", action="store_true", dest="everything", help="check every active component"
    )
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    parser.set_defaults(handler=run_check, judged=True)


def _report(args: argparse.Namespace) -> Report:
    repo, candidate = candidate_of(args)
    settings = Settings(
        tools=local_tools(),
        commands=args.command_table,
        rules={rule.id: rule for rule in build_registry()},
        today=datetime.now(UTC).date(),
        profiles=local_profiles(),
        everything=args.everything,
    )
    return check_candidate(repo, candidate, settings)


def run_check(args: argparse.Namespace) -> int:
    """Check one candidate and report every finding."""
    try:
        report = _report(args)
    except (GitioError, ToolchainError) as error:
        report = Report((error.diagnostic,))
    outcome = Outcome.of(report.diagnostics)
    if args.json:
        extra = {
            "files": report.files,
            "excepted": report.excepted,
            "tested": list(report.tested),
            "coverage": coverage_json(report.coverage),
        }
        sys.stdout.write(outcome_to_json(outcome, command=NAME, extra=extra))
    else:
        summary = (
            f"checked {report.files} files; {report.excepted} findings covered by exceptions\n"
        )
        sys.stdout.write(render_text(outcome) + coverage_text(report.coverage) + summary)
    return int(outcome.exit_code())
