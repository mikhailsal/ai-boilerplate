"""What the commands that judge a candidate share: the candidate and the coverage lines."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from quality.cli.inventory_cmd import index_from
from quality.gitio import Candidate, Repository, revision, staged
from quality.rules.coverage import ComponentCoverage


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
