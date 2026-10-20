"""`quality test`: the unit suites and coverage floors of the components a candidate affects.

Suites run in the isolated snapshot through a profile's runner. Results and
coverage are read only from a new output directory created for that run, and
coverage is evaluated only after a clean unit run (R06, decision 0008).
"""

from __future__ import annotations

import tempfile
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from quality.diagnostics import Diagnostic, Rule
from quality.discovery import (
    Inventory,
    Region,
    active_components,
    affected_components,
    build_inventory,
)
from quality.discovery.classify import under
from quality.engine.check import UNAVAILABLE, checked_policy
from quality.engine.runs import ProfileTests, run_suite, unit_coverage
from quality.gitio import (
    Candidate,
    FileChange,
    Repository,
    Snapshot,
    commit_lines,
    materialize,
    tree_changes,
)
from quality.policy import Category, Component, Policy, Profile
from quality.rules import coverage, testing
from quality.testing import Suite, SuiteRequest, suite_roots


@dataclass(frozen=True, slots=True)
class SuiteSettings:
    """Runners per profile, the known rules, and whether to test every active component."""

    runners: Mapping[Profile, ProfileTests]
    rules: Mapping[str, Rule]
    everything: bool = False
    suites: tuple[Suite, ...] = (Suite.UNIT,)


@dataclass(frozen=True, slots=True)
class SuiteReport:
    """The result of testing one candidate."""

    diagnostics: tuple[Diagnostic, ...]
    tested: tuple[str, ...] = ()
    coverage: tuple[coverage.ComponentCoverage, ...] = ()


@dataclass(frozen=True, slots=True)
class Changes:
    """What the candidate changes: lines per path and the files it adds."""

    lines: Mapping[str, frozenset[int]]
    added: frozenset[str]


def changed_paths(changes: Iterable[FileChange]) -> list[str]:
    """Every path a change touches, including the old side of a rename."""
    paths: list[str] = []
    for change in changes:
        paths.append(change.path)
        if change.old_path is not None:
            paths.append(change.old_path)
    return paths


def added_files(changes: Iterable[FileChange]) -> frozenset[str]:
    """Files whose every line is new: additions and replacements of non-files."""
    return frozenset(
        change.path
        for change in changes
        if change.status != "D"
        and change.new_is_file
        and (change.status == "A" or not change.old_is_file)
    )


def selected_components(
    policy: Policy, paths: list[str], *, everything: bool
) -> tuple[Component, ...]:
    """Active components the change affects, or every active component."""
    active = active_components(policy, paths)
    if everything:
        return active
    affected = {component.id for component in affected_components(policy, paths)}
    return tuple(component for component in active if component.id in affected)


def expectation(
    component: Component,
    snapshot: Snapshot,
    inventory: Inventory,
    runner: ProfileTests,
    changes: Changes,
) -> coverage.Expectation:
    """Derive the expected sources from the snapshot, independently of what tests import."""
    sources = frozenset(
        record.path
        for record in inventory.files
        if record.component == component.id
        and record.region is Region.SOURCE
        and record.category is Category.SOURCE
        and runner.expected(record.path)
    )
    prefix = "" if component.root == "." else component.root + "/"
    missing = tuple(
        root
        for root in component.source
        if not any(under(entry.path, prefix + root) for entry in snapshot.entries)
    )
    return coverage.Expectation(component.id, sources, missing, changes.lines, changes.added)


@dataclass(frozen=True, slots=True)
class Context:
    """Everything a component's suites need from the candidate."""

    policy: Policy
    snapshot: Snapshot
    inventory: Inventory
    changes: Changes
    suites: tuple[Suite, ...]

    def request(self, component: Component, suite: Suite) -> SuiteRequest:
        """Build a request with a new, empty output directory."""
        started = time.time()
        output = Path(tempfile.mkdtemp(prefix=f"{component.id}-{suite}-", dir=self.snapshot.work))
        roots = suite_roots(component, suite)
        return SuiteRequest(component, suite, roots, self.snapshot.root, output, started)


def component_suites(
    component: Component, runner: ProfileTests, context: Context
) -> tuple[list[Diagnostic], coverage.ComponentCoverage | None]:
    """Run a component's suites; only its own unit run can satisfy its coverage floors."""
    found: list[Diagnostic] = []
    summary = None
    for suite in context.suites:
        if not suite_roots(component, suite):
            if suite is Suite.UNIT:
                found.append(testing.missing_suite(component.id))
            continue
        request = context.request(component, suite)
        diagnostics, run = run_suite(runner, request)
        found.extend(diagnostics)
        if suite is Suite.UNIT and run is not None:
            expected = expectation(
                component, context.snapshot, context.inventory, runner, context.changes
            )
            measured, summary = unit_coverage(runner, request, run, expected, context.policy)
            found.extend(measured)
    return found, summary


def _inspect(repo: Repository, candidate: Candidate, settings: SuiteSettings) -> SuiteReport:
    with materialize(repo, candidate.tree) as snapshot:
        policy = checked_policy(snapshot.root, settings.rules)
        if isinstance(policy, tuple):
            return SuiteReport(policy)
        inventory = build_inventory(policy, snapshot.root, snapshot.entries)
        diff = tree_changes(repo, candidate.base_tree, candidate.tree)
        changes = Changes(commit_lines(repo, candidate), added_files(diff))
        context = Context(policy, snapshot, inventory, changes, settings.suites)
        selected = selected_components(policy, changed_paths(diff), everything=settings.everything)
        found: list[Diagnostic] = []
        summaries: list[coverage.ComponentCoverage] = []
        for component in selected:
            runner = settings.runners.get(component.profile)
            if runner is None:
                message = (
                    f"the {component.profile} test runner of '{component.id}' is not available"
                )
                found.append(UNAVAILABLE.diagnostic(message, component=component.id))
                continue
            diagnostics, summary = component_suites(component, runner, context)
            found.extend(diagnostics)
            if summary is not None:
                summaries.append(summary)
    return SuiteReport(tuple(found), tuple(c.id for c in selected), tuple(summaries))


def run_suites(repo: Repository, candidate: Candidate, settings: SuiteSettings) -> SuiteReport:
    """Test a candidate and confirm it did not change while its suites ran."""
    report = _inspect(repo, candidate, settings)
    candidate.verify_unchanged()
    return report
