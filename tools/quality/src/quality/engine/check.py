"""`quality check`: every gate over one isolated candidate snapshot.

The common gates cover the whole candidate. Profile gates and unit suites with
their coverage floors cover the components the change affects, or every active
component when asked; a component whose profile has no adapter fails.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date

from quality.diagnostics import Diagnostic, Rule
from quality.engine.common import (
    COMMON_RULES,
    PYTHON_RULES,
    TOOL_RULES,
    Commands,
    Tools,
    candidate_files,
    common_gates,
    tool_findings,
)
from quality.engine.profiles import ProfileAdapter
from quality.engine.scope import (
    UNAVAILABLE,
    Scope,
    candidate_scope,
    checked_policy,
    prepare_components,
    unavailable,
)
from quality.engine.suites import suite_findings
from quality.gitio import Candidate, Repository, materialize
from quality.policy import Component, Profile
from quality.rules import exceptions
from quality.rules.coverage import ComponentCoverage
from quality.testing import Suite

RULES = (UNAVAILABLE,)

type Adapters = Mapping[Profile, ProfileAdapter]
type Ready = list[tuple[Component, ProfileAdapter]]


def _no_adapters() -> Adapters:
    return {}


@dataclass(frozen=True, slots=True)
class Settings:
    """What a check needs besides the candidate."""

    tools: Tools
    commands: Commands
    rules: Mapping[str, Rule]
    today: date
    profiles: Adapters = field(default_factory=_no_adapters)
    everything: bool = False


@dataclass(frozen=True, slots=True)
class Report:
    """The result of checking one candidate."""

    diagnostics: tuple[Diagnostic, ...]
    files: int = 0
    excepted: int = 0
    tested: tuple[str, ...] = ()
    coverage: tuple[ComponentCoverage, ...] = ()


def ran_rules(
    active: Iterable[Component], checked: Iterable[Component], profiles: Adapters
) -> frozenset[str]:
    """Return the rules that ran over the whole candidate, so unused exceptions are reliable."""
    active = tuple(active)
    ran = [*COMMON_RULES, *TOOL_RULES]
    if any(component.profile is Profile.PYTHON for component in active):
        ran.extend(PYTHON_RULES)
    done = {component.id for component in checked}
    for profile, adapter in profiles.items():
        members = [component.id for component in active if component.profile is profile]
        if members and done.issuperset(members):
            ran.extend(adapter.rules)
    return frozenset(rule.id for rule in ran)


def _static(component: Component, adapter: ProfileAdapter, scope: Scope) -> list[Diagnostic]:
    snapshot = scope.snapshot
    files = scope.files(component)
    return tool_findings(lambda: adapter.static(component, snapshot.root, snapshot.work, files))


def profile_gates(
    scope: Scope, profiles: Adapters
) -> tuple[list[Diagnostic], Ready, list[ComponentCoverage]]:
    """Native gates and unit suites of the selected components."""
    found = [unavailable(c) for c in scope.active if c.profile not in profiles]
    supported = [c for c in scope.selected if c.profile in profiles]
    ready, problems = prepare_components(profiles, supported, scope.snapshot)
    found.extend(problems)
    for component, adapter in ready:
        found.extend(_static(component, adapter, scope))
    diagnostics, summaries = suite_findings(scope, ready, (Suite.UNIT,))
    found.extend(diagnostics)
    return found, ready, summaries


def _inspect(repo: Repository, candidate: Candidate, settings: Settings) -> Report:
    with materialize(repo, candidate.tree) as snapshot:
        policy = checked_policy(snapshot.root, settings.rules)
        if isinstance(policy, tuple):
            return Report(policy)
        scope = candidate_scope(repo, candidate, snapshot, policy, everything=settings.everything)
        limit = policy.thresholds.blob_bytes
        found = candidate_files(snapshot.root, snapshot.entries, scope.inventory, limit)
        common = common_gates(scope, found, tools=settings.tools, commands=settings.commands)
        gates = [*scope.inventory.diagnostics, *common]
        profiled, ready, summaries = profile_gates(scope, settings.profiles)
        checked = [component for component, _ in ready]
        applied = exceptions.apply_exceptions(
            [*gates, *profiled],
            policy.exceptions,
            rules=settings.rules,
            ran=ran_rules(scope.active, checked, settings.profiles),
            today=settings.today,
        )
    tested = tuple(component.id for component in checked)
    return Report(applied.diagnostics, len(found), applied.excepted, tested, tuple(summaries))


def check_candidate(repo: Repository, candidate: Candidate, settings: Settings) -> Report:
    """Check a candidate and confirm it did not change while it was being checked."""
    report = _inspect(repo, candidate, settings)
    candidate.verify_unchanged()
    return report
