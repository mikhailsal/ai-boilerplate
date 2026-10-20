"""The common gates over a materialized candidate and the structure of Python components."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from quality.adapters import markdown, native, secrets
from quality.adapters.python.imports import file_dependencies, import_roots
from quality.adapters.python.structure import PythonStructure
from quality.diagnostics import Diagnostic
from quality.discovery import Inventory, Region
from quality.engine.scope import Scope
from quality.gitio import TreeEntry
from quality.metrics import FileMetrics, StructureError
from quality.policy import Category, Component, Policy, Profile
from quality.rules import architecture, config, docs, files, structure, suppressions
from quality.rules.links import is_markdown
from quality.rules.model import CandidateFile

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


def tool_findings(run: Callable[[], Iterable[Diagnostic]]) -> list[Diagnostic]:
    """Run a native tool; its failure becomes its single diagnostic."""
    try:
        return list(run())
    except native.ToolFailedError as error:
        return [error.diagnostic]


def common_gates(
    scope: Scope, candidate: list[CandidateFile], *, tools: Tools, commands: Commands
) -> Iterator[Diagnostic]:
    """File, configuration, suppression, documentation, secret, and Python structure gates."""
    policy, snapshot = scope.policy, scope.snapshot
    yield from files.check_files(candidate, policy.thresholds)
    yield from config.check_config(candidate)
    yield from suppressions.check_suppressions(candidate)
    yield from docs.check_docs(candidate, policy.thresholds, commands)
    pages = [
        (file.path, file.data)
        for file in candidate
        if file.category is Category.DOCS
        and is_markdown(file.path)
        and file.data is not None
        and file.text() is not None
    ]
    if pages:
        yield from tool_findings(
            lambda: markdown.lint_markdown(pages, snapshot.work, python=tools.python)
        )

    def scan() -> Iterator[Diagnostic]:
        found = secrets.scan_directory(
            snapshot.root, snapshot.work, gitleaks=tools.gitleaks, rules=tools.gitleaks_rules
        )
        return secrets.secret_diagnostics(found)

    yield from tool_findings(scan)
    for component in scope.active:
        if component.profile is Profile.PYTHON:
            yield from python_gates(component, candidate, policy)
