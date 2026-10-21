"""`quality check` and `quality gate`: every gate over one isolated candidate snapshot.

The common gates and the static scenario checks cover the whole candidate, and
the new commits of a candidate that carries them. Profile gates, unit suites
with their coverage floors, and the suites of the scenarios mandatory at the
stage cover the components the change affects, or every active component when
asked; a component whose profile has no adapter fails.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from quality.ci import changed_control
from quality.diagnostics import Diagnostic, Rule
from quality.engine.common import (
    COMMON_MEASURED,
    COMMON_RULES,
    MEASURED_RULES,
    TOOL_RULES,
    Commands,
    Tools,
    candidate_files,
    common_gates,
    measured_gates,
    tool_findings,
)
from quality.engine.history import check_history
from quality.engine.profiles import ProfileAdapter
from quality.engine.runs import SuiteFindings, suite_findings
from quality.engine.scenarios import load_manifests, reconciled, required_at, stage_suites
from quality.engine.scope import (
    UNAVAILABLE,
    Scope,
    candidate_scope,
    checked_policy,
    prepare_components,
    unavailable,
)
from quality.gitio import Candidate, Repository, Snapshot, materialize
from quality.policy import Component, Profile, Quarantine
from quality.policy.scenarios import Stage
from quality.reports import write_evidence
from quality.rules import exceptions, quarantine
from quality.rules.coverage import ComponentCoverage
from quality.scenarios.reconcile import ScenarioSummary
from quality.testing import Suite

RULES = (UNAVAILABLE,)

type Adapters = Mapping[Profile, ProfileAdapter]
type Ready = list[tuple[Component, ProfileAdapter]]


def _no_adapters() -> Adapters:
    return {}


@dataclass(frozen=True, slots=True)
class Settings:
    """What a check needs besides the candidate.

    `reports` is a prepared directory that receives the exports and native
    reports of the suites while the snapshot exists.
    """

    tools: Tools
    commands: Commands
    rules: Mapping[str, Rule]
    today: date
    profiles: Adapters = field(default_factory=_no_adapters)
    everything: bool = False
    stage: Stage = Stage.COMMIT
    reports: Path | None = None


@dataclass(frozen=True, slots=True)
class Report:
    """The result of checking one candidate."""

    diagnostics: tuple[Diagnostic, ...]
    files: int = 0
    excepted: int = 0
    tested: tuple[str, ...] = ()
    coverage: tuple[ComponentCoverage, ...] = ()
    scenarios: tuple[ScenarioSummary, ...] = ()


def _own_rules(profile: Profile, adapter: ProfileAdapter | None) -> frozenset[str]:
    """Return the rules that run over a component's files only when it is checked."""
    rules = adapter.rules if adapter is not None else ()
    measured = () if profile in COMMON_MEASURED else MEASURED_RULES
    return frozenset(rule.id for rule in (*rules, *measured))


def ran_rules(
    active: Iterable[Component], checked: Iterable[Component], profiles: Adapters
) -> exceptions.Ran:
    """Return the rules that ran and where, so unused exceptions are reliable.

    The common gates run everywhere, and they measure every Python component. A
    component's adapter rules, and the structure rules of profiles whose adapter
    measures, ran only over the files of components that were checked.
    """
    active = tuple(active)
    ran = {rule.id for rule in (*COMMON_RULES, *TOOL_RULES)}
    if any(component.profile in COMMON_MEASURED for component in active):
        ran.update(rule.id for rule in MEASURED_RULES)
    done = {component.id for component in checked}
    skipped: dict[str, frozenset[str]] = {}
    for component in active:
        own = _own_rules(component.profile, profiles.get(component.profile))
        if component.id in done:
            ran.update(own)
        skipped[component.root] = frozenset() if component.id in done else own
    return exceptions.Ran(frozenset(ran), skipped)


def _static(component: Component, adapter: ProfileAdapter, scope: Scope) -> list[Diagnostic]:
    request = scope.static_request(component)
    found = tool_findings(lambda: adapter.static(request))

    def measured() -> list[Diagnostic]:
        measurements = adapter.measure(request)
        if measurements is None:
            return []
        sources = scope.sources(component)
        thresholds = scope.policy.thresholds
        return list(measured_gates(component, measurements, thresholds, sources))

    found.extend(tool_findings(measured))
    return found


def profile_gates(
    scope: Scope,
    profiles: Adapters,
    plan: Callable[[Component], Iterable[Suite]],
    held: Sequence[Quarantine] = (),
) -> tuple[list[Diagnostic], Ready, SuiteFindings]:
    """Native gates and the suites each selected component's plan names."""
    found = [unavailable(c) for c in scope.active if c.profile not in profiles]
    supported = [c for c in scope.selected if c.profile in profiles]
    ready, problems = prepare_components(profiles, supported, scope.snapshot)
    found.extend(problems)
    for component, adapter in ready:
        found.extend(_static(component, adapter, scope))
    findings = suite_findings(scope, ready, plan, held)
    found.extend(findings.diagnostics)
    return found, ready, findings


def history_gates(
    repo: Repository, candidate: Candidate, snapshot: Snapshot, tools: Tools, limit: int
) -> list[Diagnostic]:
    """Check every blob of the candidate's new commits, when it carries them (R04)."""
    if candidate.history is None:
        return []
    work = Path(tempfile.mkdtemp(prefix="history-", dir=snapshot.work))
    return check_history(repo, candidate.history, work, tools=tools, blob_limit=limit)


def control_changes(scope: Scope, stage: Stage) -> list[Diagnostic]:
    """List the changed control files at the merge stage of a policy with `[ci]`."""
    ci = scope.policy.ci
    if ci is None or stage is not Stage.MERGE:
        return []
    return list(changed_control(scope.policy, ci, scope.inventory.files, scope.changes.paths))


def _inspect(repo: Repository, candidate: Candidate, settings: Settings) -> Report:
    with materialize(repo, candidate.tree) as snapshot:
        policy = checked_policy(snapshot.root, settings.rules)
        if isinstance(policy, tuple):
            return Report(policy)
        scope = candidate_scope(repo, candidate, snapshot, policy, everything=settings.everything)
        limit = policy.thresholds.blob_bytes
        found = candidate_files(snapshot.root, snapshot.entries, scope.inventory, limit)
        common = common_gates(scope, found, tools=settings.tools, commands=settings.commands)
        history = history_gates(repo, candidate, snapshot, settings.tools, limit)
        manifests = load_manifests(repo, candidate.base_tree, scope)
        held, expired = quarantine.current(policy.quarantine, settings.today)
        gates = [
            *scope.inventory.diagnostics,
            *common,
            *history,
            *control_changes(scope, settings.stage),
            *manifests.diagnostics,
            *expired,
        ]

        def plan(component: Component) -> tuple[Suite, ...]:
            return stage_suites(manifests.subjects.get(component.id), settings.stage)

        profiled, ready, findings = profile_gates(scope, settings.profiles, plan, held)
        proved, scenarios = reconciled(manifests, findings.ran, required_at(settings.stage), held)
        if settings.reports is not None:
            proved.extend(write_evidence(settings.reports, snapshot.root, findings.evidence))
        checked = [component for component, _ in ready]
        applied = exceptions.apply_exceptions(
            [*gates, *profiled, *proved],
            policy.exceptions,
            rules=settings.rules,
            ran=ran_rules(scope.active, checked, settings.profiles),
            today=settings.today,
        )
    tested = tuple(component.id for component in checked)
    return Report(
        applied.diagnostics,
        len(found),
        applied.excepted,
        tested,
        tuple(findings.coverage),
        tuple(scenarios),
    )


def check_candidate(repo: Repository, candidate: Candidate, settings: Settings) -> Report:
    """Check a candidate and confirm it did not change while it was being checked."""
    report = _inspect(repo, candidate, settings)
    candidate.verify_unchanged()
    return report
