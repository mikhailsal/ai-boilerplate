"""What the commands that judge a candidate share: the candidate, coverage, and scenarios."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from quality.cli.inventory_cmd import index_from
from quality.gitio import Candidate, Repository, revision, staged
from quality.rules.coverage import ComponentCoverage
from quality.scenarios.reconcile import ScenarioSummary


def candidate_of(args: argparse.Namespace) -> tuple[Repository, Candidate]:
    """Return the repository and the candidate: `--rev`, or the index a hook selected."""
    repo = Repository.discover(Path.cwd(), os.environ)
    rev: str | None = args.rev
    if rev is not None:
        return repo, revision(repo, rev)
    return repo, staged(repo, index_from(os.environ, Path.cwd()))


def coverage_text(summaries: tuple[ComponentCoverage, ...]) -> str:
    """Describe the unit coverage of each tested component, one line each."""
    lines: list[str] = []
    for summary in summaries:
        branch = summary.branch.describe() if summary.branch is not None else "not measured"
        lines.append(
            f"unit coverage of {summary.component}: line {summary.line.describe()}, "
            f"branch {branch}, changed lines {summary.changed.describe()}\n"
        )
    return "".join(lines)


def coverage_json(summaries: tuple[ComponentCoverage, ...]) -> list[dict[str, object]]:
    """Return the unit coverage of each tested component as JSON-ready counters."""
    found: list[dict[str, object]] = []
    for summary in summaries:
        counters = {"line": summary.line, "branch": summary.branch, "changed": summary.changed}
        found.append(
            {
                "component": summary.component,
                **{
                    name: None if c is None else {"covered": c.covered, "total": c.total}
                    for name, c in counters.items()
                },
            }
        )
    return found


def scenarios_text(summaries: tuple[ScenarioSummary, ...]) -> str:
    """Describe how many scenarios of each reconciled component this run proved."""
    lines: list[str] = []
    for summary in summaries:
        line = f"scenarios of {summary.component}: {summary.passed} of {summary.required} proved"
        line += f", {summary.suspended} suspended" if summary.suspended else ""
        line += f", {summary.deferred} not required by this run" if summary.deferred else ""
        lines.append(line + "\n")
    return "".join(lines)


def scenarios_json(summaries: tuple[ScenarioSummary, ...]) -> list[dict[str, object]]:
    """Return the scenario counts of each reconciled component."""
    return [
        {
            "component": summary.component,
            "required": summary.required,
            "proved": summary.passed,
            "suspended": summary.suspended,
            "deferred": summary.deferred,
        }
        for summary in summaries
    ]
