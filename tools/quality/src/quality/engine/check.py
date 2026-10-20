"""`quality check`: the common gates over one isolated candidate snapshot."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from quality.adapters import markdown, native, secrets
from quality.adapters.python.imports import file_dependencies, import_roots
from quality.adapters.python.structure import PythonStructure
from quality.diagnostics import Diagnostic, Kind, Rule
from quality.discovery import Inventory, Region, active_components, build_inventory
from quality.gitio import Candidate, Repository, Snapshot, TreeEntry, materialize, tree_changes
from quality.metrics import FileMetrics, StructureError
from quality.policy import Category, Component, Policy, Profile, cross_validate, load_policy
from quality.rules import architecture, config, docs, exceptions, files, structure, suppressions
from quality.rules.links import is_markdown
from quality.rules.model import CandidateFile

UNAVAILABLE = Rule(
    id="profiles.unavailable",
    title="Profile gates are not available in this build",
    requirement="R01",
    explanation=(
        "An active component uses a profile whose adapter is not implemented yet, so its "
        "formatting, lint, type, structure, and test gates cannot run. Nothing passes silently."
    ),
    remedy="Use a supported profile or update the boilerplate to a version that provides it.",
    kind=Kind.ENVIRONMENT,
)
RULES = (UNAVAILABLE,)

COMMON_RULES = (*files.RULES, *config.RULES, *suppressions.RULES, *docs.RULES)
TOOL_RULES = (*markdown.RULES, *secrets.RULES)
PYTHON_RULES = (*structure.RULES, *architecture.RULES)
STRUCTURE_SUFFIXES = frozenset({".py"})

type Commands = Mapping[str, frozenset[str]]


@dataclass(frozen=True, slots=True)
class Tools:
    """Executables and data files the common gates use; all pinned and local."""

    python: Path
    gitleaks: Path
    gitleaks_rules: Path


@dataclass(frozen=True, slots=True)
class Report:
    """The result of checking one candidate."""

    diagnostics: tuple[Diagnostic, ...]
    files: int = 0
    excepted: int = 0


def _read(root: Path, path: str) -> bytes:
    descriptor = os.open(root / path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        return stream.read()


def candidate_files(
    root: Path, entries: Iterable[TreeEntry], inventory: Inventory, limit: int
) -> list[CandidateFile]:
    """Pair records with sizes and, for regular files within the blob limit, bytes."""
    records = {record.path: record for record in inventory.files}
    found: list[CandidateFile] = []
    for entry in entries:
        record = records[entry.path]
        readable = entry.is_file and entry.size <= limit
        found.append(
            CandidateFile(record, entry.size, _read(root, entry.path) if readable else None)
        )
    return found


def _measured(files: Iterable[CandidateFile], component: Component) -> Iterator[CandidateFile]:
    for file in files:
        if (
            file.record.component == component.id
            and file.category in {Category.SOURCE, Category.TESTS}
            and file.record.language == "python"
            and PurePosixPath(file.path).suffix in STRUCTURE_SUFFIXES
            and file.data is not None
        ):
            yield file


def python_gates(
    component: Component, files: list[CandidateFile], policy: Policy
) -> Iterator[Diagnostic]:
    """Structure metrics and module architecture of one Python component."""
    analyzer = PythonStructure()
    sources: dict[str, FileMetrics] = {}
    for file in _measured(files, component):
        try:
            metrics = analyzer.analyze(file.path, file.data or b"")
        except StructureError as error:
            yield structure.unparseable(error, component=component.id)
            continue
        yield from structure.check_structure(metrics, policy.thresholds, component=component.id)
        if file.record.region is Region.SOURCE:
            sources[file.path] = metrics
    if component.architecture.modules:
        prefix = "" if component.root == "." else component.root + "/"
        roots = import_roots([prefix + root for root in component.source], sources)
        edges = file_dependencies(sources, roots)
        yield from architecture.check_architecture(component, sorted(sources), edges)


@dataclass(frozen=True, slots=True)
class Settings:
    """What a check needs besides the candidate."""

    tools: Tools
    commands: Commands
    rules: Mapping[str, Rule]
    today: date


def _tool(run: Callable[[], Iterable[Diagnostic]]) -> list[Diagnostic]:
    try:
        return list(run())
    except native.ToolFailedError as error:
        return [error.diagnostic]


def _gates(
    policy: Policy,
    active: tuple[Component, ...],
    candidate: list[CandidateFile],
    snapshot: Snapshot,
    settings: Settings,
) -> Iterator[Diagnostic]:
    tools = settings.tools
    yield from files.check_files(candidate, policy.thresholds)
    yield from config.check_config(candidate)
    yield from suppressions.check_suppressions(candidate)
    yield from docs.check_docs(candidate, policy.thresholds, settings.commands)
    pages = [
        (file.path, file.data)
        for file in candidate
        if file.category is Category.DOCS
        and is_markdown(file.path)
        and file.data is not None
        and file.text() is not None
    ]
    if pages:
        yield from _tool(lambda: markdown.lint_markdown(pages, snapshot.work, python=tools.python))

    def scan() -> Iterator[Diagnostic]:
        found = secrets.scan_directory(
            snapshot.root, snapshot.work, gitleaks=tools.gitleaks, rules=tools.gitleaks_rules
        )
        return secrets.secret_diagnostics(found)

    yield from _tool(scan)
    for component in active:
        if component.profile is Profile.PYTHON:
            yield from python_gates(component, candidate, policy)
        else:
            message = f"the {component.profile} profile of '{component.id}' is not available yet"
            yield UNAVAILABLE.diagnostic(message, component=component.id)


def ran_rules(active: Iterable[Component]) -> frozenset[str]:
    """Return the rules that ran over the whole candidate, so unused exceptions are reliable."""
    ran = [*COMMON_RULES, *TOOL_RULES]
    if any(component.profile is Profile.PYTHON for component in active):
        ran.extend(PYTHON_RULES)
    return frozenset(rule.id for rule in ran)


def checked_policy(root: Path, rules: Iterable[str]) -> Policy | tuple[Diagnostic, ...]:
    """Load and cross-validate the snapshot's policy, or return why it is unusable."""
    loaded = load_policy(root)
    if loaded.policy is None:
        return tuple(loaded.diagnostics)
    problems = cross_validate(loaded.policy, frozenset(rules))
    return tuple(problems) if problems else loaded.policy


def _inspect(repo: Repository, candidate: Candidate, settings: Settings) -> Report:
    with materialize(repo, candidate.tree) as snapshot:
        policy = checked_policy(snapshot.root, settings.rules)
        if isinstance(policy, tuple):
            return Report(policy)
        inventory = build_inventory(policy, snapshot.root, snapshot.entries)
        changed = [
            change.path for change in tree_changes(repo, candidate.base_tree, candidate.tree)
        ]
        active = active_components(policy, changed)
        limit = policy.thresholds.blob_bytes
        found = candidate_files(snapshot.root, snapshot.entries, inventory, limit)
        gates = _gates(policy, active, found, snapshot, settings)
        applied = exceptions.apply_exceptions(
            [*inventory.diagnostics, *gates],
            policy.exceptions,
            rules=settings.rules,
            ran=ran_rules(active),
            today=settings.today,
        )
    return Report(applied.diagnostics, len(found), applied.excepted)


def check_candidate(repo: Repository, candidate: Candidate, settings: Settings) -> Report:
    """Check a candidate and confirm it did not change while it was being checked."""
    report = _inspect(repo, candidate, settings)
    candidate.verify_unchanged()
    return report
