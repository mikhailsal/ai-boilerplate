from dataclasses import dataclass, field
from pathlib import Path

import pytest

from quality.adapters import native
from quality.catalog import build_registry
from quality.diagnostics import Diagnostic, Severity
from quality.engine.setup import (
    SetupReport,
    Staged,
    hook_status,
    install_hooks,
    probe_components,
    provision_components,
)
from quality.gitio import Repository
from quality.hooks import HookName, script
from quality.policy import Component, Profile
from quality.testkit.gitrepo import GitRepo
from quality.testkit.policies import ComponentSpec, policy_toml

RULES = tuple(rule.id for rule in build_registry())
APP = ComponentSpec(root="app")
WEB = ComponentSpec(id="web", root="web", profile="typescript")
STALE = native.FAILED.diagnostic("uv sync: app: package not cached")
FOREIGN = b"#!/bin/sh\necho my own hook\n"


@dataclass
class Setup:
    """A profile setup that records what it saw and returns or raises what it was given."""

    remaining: list[Diagnostic] = field(default_factory=list[Diagnostic])
    error: native.ToolFailedError | None = None
    calls: list[tuple[str, str, Path]] = field(default_factory=list[tuple[str, str, Path]])
    seen: list[str] = field(default_factory=list[str])

    def _step(self, step: str, component: Component, root: Path) -> list[Diagnostic]:
        self.calls.append((step, component.id, root))
        self.seen.extend(sorted(p.relative_to(root).as_posix() for p in root.rglob("*.py")))
        if self.error is not None:
            raise self.error
        return self.remaining

    def provision(self, component: Component, root: Path) -> list[Diagnostic]:
        return self._step("provision", component, root)

    def probe(self, component: Component, root: Path) -> list[Diagnostic]:
        return self._step("probe", component, root)


@pytest.fixture
def project(repo: GitRepo) -> GitRepo:
    repo.write("quality.toml", policy_toml(APP, WEB))
    repo.write("app/src/app/core.py", "x = 1\n")
    repo.write("app/tests/test_core.py", "")
    repo.write("web/src/index.ts", "")
    repo.write("web/tests/index.test.ts", "")
    repo.commit_all("base")
    return repo


def hook(repo: GitRepo, name: HookName = HookName.PRE_COMMIT) -> Path:
    return repo.path / ".git" / "hooks" / str(name)


def rules_of(report: SetupReport) -> list[str]:
    return [d.rule for d in report.diagnostics]


def test_provision_reads_the_staged_candidate_in_a_snapshot(project: GitRepo) -> None:
    project.write("app/src/app/staged.py", "")
    project.git("add", "app/src/app/staged.py")
    project.write("app/src/app/untracked.py", "")
    python = Setup()
    report = provision_components(Staged(project.repository()), {Profile.PYTHON: python}, RULES)
    assert report.lines == ["app: the python environment is ready"]
    assert [(d.rule, d.component) for d in report.diagnostics] == [("profiles.unavailable", "web")]
    assert "environment setup for it" in report.diagnostics[0].message
    ((step, component, root),) = python.calls
    assert (step, component) == ("provision", "app")
    assert root != project.path
    assert not root.exists()
    assert python.seen == [
        "app/src/app/core.py",
        "app/src/app/staged.py",
        "app/tests/test_core.py",
    ]


def test_probe_runs_the_probe_step(project: GitRepo) -> None:
    python, typescript = Setup(), Setup()
    setups = {Profile.PYTHON: python, Profile.TYPESCRIPT: typescript}
    report = probe_components(Staged(project.repository()), setups, RULES)
    assert report == SetupReport(
        [],
        ["app: the python environment is ready", "web: the typescript environment is ready"],
    )
    assert [call[:2] for call in python.calls + typescript.calls] == [
        ("probe", "app"),
        ("probe", "web"),
    ]


@pytest.mark.parametrize("python", [Setup([STALE]), Setup(error=native.failure("uv", "boom"))])
def test_a_component_with_problems_is_not_ready(project: GitRepo, python: Setup) -> None:
    setups = {Profile.PYTHON: python, Profile.TYPESCRIPT: Setup()}
    report = probe_components(Staged(project.repository()), setups, RULES)
    assert rules_of(report) == ["tools.failed"]
    assert report.lines == ["web: the typescript environment is ready"]


def test_an_alternate_index_is_the_candidate(project: GitRepo, tmp_path: Path) -> None:
    index = tmp_path / "index"
    project.git("read-tree", "HEAD", GIT_INDEX_FILE=str(index))
    project.git("rm", "-q", "--cached", "app/tests/test_core.py", GIT_INDEX_FILE=str(index))
    python = Setup()
    target = Staged(project.repository(), index)
    provision_components(target, {Profile.PYTHON: python, Profile.TYPESCRIPT: Setup()}, RULES)
    assert python.seen == ["app/src/app/core.py"]


def test_an_unusable_policy_is_reported_without_setting_up(project: GitRepo) -> None:
    project.git("rm", "-q", "--cached", "quality.toml")
    python = Setup()
    report = provision_components(Staged(project.repository()), {Profile.PYTHON: python}, RULES)
    assert rules_of(report) == ["policy.missing"]
    assert (report.lines, python.calls) == ([], [])


def test_a_git_failure_is_reported(project: GitRepo, tmp_path: Path) -> None:
    index = tmp_path / "index"
    index.write_bytes(b"not an index")
    python = Setup()
    report = probe_components(Staged(project.repository(), index), {Profile.PYTHON: python}, RULES)
    assert rules_of(report) == ["git.failed"]
    assert (report.lines, python.calls) == ([], [])


def test_reports_merge_in_order() -> None:
    first = SetupReport([STALE], ["one"])
    first.merge(SetupReport([STALE], ["two"]))
    assert first == SetupReport([STALE, STALE], ["one", "two"])


def test_hooks_are_installed_and_reported_current(repo: GitRepo) -> None:
    git = repo.repository()
    report = install_hooks(git, HookName)
    assert report == SetupReport([], [f"{name} hook: {hook(repo, name)}" for name in HookName])
    assert hook(repo).read_text() == script(HookName.PRE_COMMIT)
    assert install_hooks(git, [HookName.PRE_COMMIT]).lines == [f"pre-commit hook: {hook(repo)}"]
    status = hook_status(git, frozenset(HookName))
    assert status == SetupReport([], ["pre-commit hook: current", "pre-push hook: current"])


def test_a_foreign_hook_is_kept_and_reported(repo: GitRepo) -> None:
    hook(repo).write_bytes(FOREIGN)
    report = install_hooks(repo.repository(), HookName)
    assert rules_of(report) == ["hooks.conflict"]
    assert report.lines == [f"pre-push hook: {hook(repo, HookName.PRE_PUSH)}"]
    assert hook(repo).read_bytes() == FOREIGN


def test_hook_status_reports_missing_and_foreign_hooks(repo: GitRepo) -> None:
    hook(repo).write_bytes(FOREIGN)
    report = hook_status(repo.repository(), frozenset(HookName))
    assert rules_of(report) == ["hooks.conflict", "hooks.missing"]
    assert report.lines == ["pre-commit hook: foreign", "pre-push hook: missing"]


def test_an_optional_outdated_hook_is_a_warning(repo: GitRepo) -> None:
    git = repo.repository()
    install_hooks(git, [HookName.PRE_PUSH])
    hook(repo, HookName.PRE_PUSH).chmod(0o644)
    report = hook_status(git, frozenset({HookName.PRE_COMMIT}))
    assert [(d.rule, d.severity) for d in report.diagnostics] == [
        ("hooks.missing", Severity.ERROR),
        ("hooks.missing", Severity.WARNING),
    ]
    assert report.lines == ["pre-commit hook: missing", "pre-push hook: outdated"]


def test_a_hooks_path_is_a_conflict(repo: GitRepo) -> None:
    repo.git("config", "core.hooksPath", ".githooks")
    git = repo.repository()
    installed = install_hooks(git, HookName)
    assert (rules_of(installed), installed.lines) == (["hooks.conflict"] * 2, [])
    status = hook_status(git, frozenset(HookName))
    assert (rules_of(status), status.lines) == (["hooks.conflict"], [])
    assert not (repo.path / ".githooks").exists()


def test_an_unreadable_git_config_is_a_git_failure(repo: GitRepo) -> None:
    git = Repository(repo.path, repo.path / ".git", repo.environ())
    (repo.path / ".git" / "config").write_text("[core\n")
    installed = install_hooks(git, [HookName.PRE_COMMIT])
    assert (rules_of(installed), installed.lines) == (["git.failed"], [])
    status = hook_status(git, frozenset(HookName))
    assert (rules_of(status), status.lines) == (["git.failed"], [])
