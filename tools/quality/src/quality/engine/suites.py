"""`quality test`: the suites and coverage floors of the components a candidate affects.

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

from quality.diagnostics import Diagnostic, Kind, Rule
from quality.discovery import Region
from quality.discovery.classify import under
from quality.engine.profiles import ProfileTests
from quality.engine.runs import run_suite, unit_coverage
from quality.engine.scope import Scope, candidate_scope, checked_policy, prepare_components
from quality.gitio import Candidate, Repository, materialize
from quality.policy import Category, Component, Profile, Role
from quality.rules import coverage, testing
from quality.testing import Suite, SuiteRequest, suite_roots

UNKNOWN = Rule(
    id="tests.unknown-component",
    title="A requested component is not an active component",
    requirement="R06",
    explanation=(
        "`quality test --component` and `quality self-test` run the suites of named "
        "components. A name that the policy does not declare, or whose component is not "
        "active in the candidate, would test nothing, so it is a usage error."
    ),
    remedy="Name an active component from quality.toml; `quality inventory` lists them.",
    kind=Kind.USAGE,
)
UNDECLARED = Rule(
    id="tests.undeclared",
    title="No selected component declares the requested suite",
    requirement="R06",
    explanation=(
        "A suite was requested explicitly, but none of the selected components declares "
        "test roots for it, so nothing would run."
    ),
    remedy="Declare the suite's roots under the component's `tests` table, or omit it.",
    kind=Kind.USAGE,
)
RULES = (UNKNOWN, UNDECLARED)


@dataclass(frozen=True, slots=True)
class SuiteSettings:
    """Runners per profile, the known rules, and which components and suites to run.

    Named `components`, or every active component with `role`, replace the affected
    selection; `required` suites must be declared by at least one selected component.
    """

    runners: Mapping[Profile, ProfileTests]
    rules: Mapping[str, Rule]
    everything: bool = False
    suites: tuple[Suite, ...] = (Suite.UNIT,)
    components: frozenset[str] = frozenset()
    role: Role | None = None
    required: bool = False


@dataclass(frozen=True, slots=True)
class SuiteReport:
    """The result of testing one candidate."""

    diagnostics: tuple[Diagnostic, ...]
    tested: tuple[str, ...] = ()
    coverage: tuple[coverage.ComponentCoverage, ...] = ()


def expectation(component: Component, scope: Scope, runner: ProfileTests) -> coverage.Expectation:
    """Derive the expected sources from the snapshot, independently of what tests import."""
    sources = frozenset(
        record.path
        for record in scope.inventory.files
        if record.component == component.id
        and record.region is Region.SOURCE
        and record.category is Category.SOURCE
        and runner.expected(record.path)
    )
    prefix = "" if component.root == "." else component.root + "/"
    missing = tuple(
        root
        for root in component.source
        if not any(under(entry.path, prefix + root) for entry in scope.snapshot.entries)
    )
    changes = scope.changes
    return coverage.Expectation(component.id, sources, missing, changes.lines, changes.added)


def request(scope: Scope, component: Component, suite: Suite) -> SuiteRequest:
    """Build a request with a new, empty output directory."""
    snapshot = scope.snapshot
    started = time.time()
    output = Path(tempfile.mkdtemp(prefix=f"{component.id}-{suite}-", dir=snapshot.work))
    roots = suite_roots(component, suite)
    return SuiteRequest(component, suite, roots, snapshot.root, output, started, snapshot.work)


def component_suites(
    component: Component, runner: ProfileTests, scope: Scope, suites: Iterable[Suite]
) -> tuple[list[Diagnostic], coverage.ComponentCoverage | None]:
    """Run a component's suites; only its own unit run can satisfy its coverage floors."""
    found: list[Diagnostic] = []
    summary = None
    for suite in suites:
        if not suite_roots(component, suite):
            if suite is Suite.UNIT:
                found.append(testing.missing_suite(component.id))
            continue
        current = request(scope, component, suite)
        diagnostics, run = run_suite(runner, current)
        found.extend(diagnostics)
        if suite is Suite.UNIT and run is not None:
            expected = expectation(component, scope, runner)
            measured, summary = unit_coverage(runner, current, run, expected, scope.policy)
            found.extend(measured)
    return found, summary


def suite_findings(
    scope: Scope, ready: Iterable[tuple[Component, ProfileTests]], suites: Iterable[Suite]
) -> tuple[list[Diagnostic], list[coverage.ComponentCoverage]]:
    """Run the suites of prepared components and collect their coverage summaries."""
    found: list[Diagnostic] = []
    summaries: list[coverage.ComponentCoverage] = []
    for component, runner in ready:
        diagnostics, summary = component_suites(component, runner, scope, suites)
        found.extend(diagnostics)
        if summary is not None:
            summaries.append(summary)
    return found, summaries


type Selection = tuple[tuple[Component, ...], list[Diagnostic]]


def declares(component: Component, suites: Iterable[Suite]) -> bool:
    """Whether the component declares roots for any of the suites."""
    return any(suite_roots(component, suite) for suite in suites)


def _by_name(scope: Scope, names: frozenset[str]) -> Selection:
    active = {component.id for component in scope.active}
    unknown = [
        UNKNOWN.diagnostic(f"'{name}' is not an active component")
        for name in sorted(names - active)
    ]
    return tuple(c for c in scope.active if c.id in names), unknown


def _by_role(scope: Scope, role: Role) -> Selection:
    selected = tuple(c for c in scope.active if c.role is role)
    missing = [] if selected else [UNKNOWN.diagnostic(f"no active component has the {role} role")]
    return selected, missing


def _undeclared(selected: tuple[Component, ...], suites: Iterable[Suite]) -> list[Diagnostic]:
    names = ", ".join(component.id for component in selected)
    return [
        UNDECLARED.diagnostic(f"no {suite} suite is declared by {names}")
        for suite in suites
        if not any(declares(component, (suite,)) for component in selected)
    ]


def named_components(scope: Scope, settings: SuiteSettings) -> Selection:
    """Resolve the components to test and check that the requested suites exist."""
    selected = scope.selected
    found: list[Diagnostic] = []
    if settings.components:
        selected, found = _by_name(scope, settings.components)
    if settings.role is not None:
        selected, missing = _by_role(scope, settings.role)
        found.extend(missing)
    if settings.required and selected:
        found.extend(_undeclared(selected, settings.suites))
    if Suite.UNIT not in settings.suites:
        # Every component needs a unit suite; the other levels concern only those declaring them.
        selected = tuple(c for c in selected if declares(c, settings.suites))
    return selected, found


def _inspect(repo: Repository, candidate: Candidate, settings: SuiteSettings) -> SuiteReport:
    with materialize(repo, candidate.tree) as snapshot:
        policy = checked_policy(snapshot.root, settings.rules)
        if isinstance(policy, tuple):
            return SuiteReport(policy)
        scope = candidate_scope(repo, candidate, snapshot, policy, everything=settings.everything)
        selected, problems = named_components(scope, settings)
        if problems:
            return SuiteReport(tuple(problems))
        ready, found = prepare_components(settings.runners, selected, snapshot)
        diagnostics, summaries = suite_findings(scope, ready, settings.suites)
    tested = tuple(component.id for component, _ in ready)
    return SuiteReport((*found, *diagnostics), tested, tuple(summaries))


def run_suites(repo: Repository, candidate: Candidate, settings: SuiteSettings) -> SuiteReport:
    """Test a candidate and confirm it did not change while its suites ran."""
    report = _inspect(repo, candidate, settings)
    candidate.verify_unchanged()
    return report
