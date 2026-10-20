"""`quality check`: run the common gates over the staged candidate or a revision."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from quality.catalog import build_registry
from quality.cli import Subcommands
from quality.cli.inventory_cmd import index_from
from quality.diagnostics import Outcome
from quality.diagnostics.render import outcome_to_json, render_text
from quality.engine import Report, Settings, Tools, check_candidate
from quality.gitio import GitioError, Repository, revision, staged
from quality.toolchain import (
    ManifestError,
    ToolchainError,
    cache_root,
    extra_path,
    load_manifest,
    locate,
)
from quality.toolchain.install import MISSING

NAME = "check"
ACTIONS: frozenset[str] = frozenset()


def register(commands: Subcommands) -> None:
    """Add the `check` subcommand."""
    parser = commands.add_parser(
        NAME,
        help="run the common gates over the staged candidate or a revision",
        description="Materialize the candidate (the index by default, or --rev) in isolation "
        "and run the repository, documentation, secret, structure, and architecture gates. "
        "Exit 0 on pass, 1 on violations, 2 on policy errors, 3 on environment errors.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--staged", action="store_true", help="check the Git index (default)")
    source.add_argument("--rev", help="check a commit instead of the index")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    parser.set_defaults(handler=run_check)


def local_tools() -> Tools:
    """Locate the pinned tools in the cache; nothing is downloaded during a check."""
    try:
        tool = load_manifest().tools["gitleaks"]
    except (ManifestError, KeyError) as error:
        raise ToolchainError(MISSING.diagnostic(f"toolchain manifest: {error}")) from error
    root = cache_root()
    gitleaks = locate("gitleaks", tool, root)
    rules = extra_path("gitleaks", tool, root, "gitleaks.toml")
    if not rules.is_file():
        message = f"gitleaks rule set is not installed (expected {rules})"
        raise ToolchainError(MISSING.diagnostic(message))
    return Tools(python=Path(sys.executable), gitleaks=gitleaks, gitleaks_rules=rules)


def _report(args: argparse.Namespace) -> Report:
    repo = Repository.discover(Path.cwd(), os.environ)
    candidate = (
        revision(repo, args.rev)
        if args.rev is not None
        else staged(repo, index_from(os.environ, Path.cwd()))
    )
    registry = build_registry()
    settings = Settings(
        tools=local_tools(),
        commands=args.command_table,
        rules={rule.id: rule for rule in registry},
        today=datetime.now(UTC).date(),
    )
    return check_candidate(repo, candidate, settings)


def run_check(args: argparse.Namespace) -> int:
    """Check one candidate and report every finding."""
    try:
        report = _report(args)
    except GitioError as error:
        report = Report((error.diagnostic,))
    except ToolchainError as error:
        report = Report((error.diagnostic,))
    outcome = Outcome.of(report.diagnostics)
    if args.json:
        extra = {"files": report.files, "excepted": report.excepted}
        sys.stdout.write(outcome_to_json(outcome, command=NAME, extra=extra))
    else:
        summary = (
            f"checked {report.files} files; {report.excepted} findings covered by exceptions\n"
        )
        sys.stdout.write(render_text(outcome) + summary)
    return int(outcome.exit_code())
