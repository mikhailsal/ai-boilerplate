import argparse
import sys
from pathlib import Path

import pytest

from quality.adapters.python.fixer import PythonFixer
from quality.adapters.python.profile import PythonProfile
from quality.adapters.python.provision import PythonSetup
from quality.cli import local
from quality.cli.local import (
    candidate_of,
    core_tool,
    coverage_json,
    coverage_text,
    local_fixers,
    local_profiles,
    local_setups,
    local_tools,
    local_uv,
    pinned,
)
from quality.coverage import Counter
from quality.policy import Profile
from quality.rules.coverage import ComponentCoverage
from quality.testkit.gitrepo import GitRepo
from quality.toolchain import ManifestError, ToolchainError, cache_root, load_manifest, python_root

SUMMARIES = (
    ComponentCoverage("a", Counter(3, 4), Counter(1, 2), Counter(0, 0)),
    ComponentCoverage("b", Counter(1, 1), None, Counter(1, 1)),
)


def missing(call: object) -> str:
    assert callable(call)
    with pytest.raises(ToolchainError) as raised:
        call()
    return raised.value.diagnostic.message


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GitRepo:
    repo = GitRepo.create(tmp_path / "repo")
    repo.write("a.txt", "first\n")
    repo.commit_all("first")
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(repo.home))
    monkeypatch.chdir(repo.path)
    return repo


def test_pinned_tools_come_from_the_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    assert pinned("uv") == load_manifest().tools["uv"]
    assert missing(lambda: pinned("no-such-tool")) == "toolchain manifest: 'no-such-tool'"

    def broken() -> object:
        msg = "bad manifest"
        raise ManifestError(msg)

    monkeypatch.setattr(local, "load_manifest", broken)
    assert missing(lambda: pinned("uv")) == "toolchain manifest: bad manifest"


def test_the_common_gate_tools_are_located_in_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = local_tools()
    assert tools.python == Path(sys.executable)
    assert tools.gitleaks_rules.is_file()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert "gitleaks" in missing(local_tools)
    tool = pinned("gitleaks")
    binary = cache_root() / f"gitleaks-{tool.version}" / tool.binary
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    assert missing(local_tools).startswith("gitleaks rule set is not installed")


def test_uv_is_located_with_its_managed_interpreters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    uv = local_uv()
    assert uv.executable.is_file()
    assert uv.pythons == python_root()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert missing(local_uv).startswith(f"uv {pinned('uv').version} is not installed")


def test_core_tools_live_beside_the_core_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert core_tool("ruff") == Path(sys.executable).parent / "ruff"
    assert missing(lambda: core_tool("no-such-tool")).startswith("no-such-tool is not installed")
    (tmp_path / "ruff").write_text("not executable\n")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    expected = f"ruff is not installed in the core environment (expected {tmp_path / 'ruff'})"
    assert missing(lambda: core_tool("ruff")) == expected


def test_the_python_profile_uses_the_installed_tools() -> None:
    profiles = local_profiles()
    assert list(profiles) == [Profile.PYTHON]
    python = profiles[Profile.PYTHON]
    assert isinstance(python, PythonProfile)
    assert (python.ruff, python.pyright) == (core_tool("ruff"), core_tool("pyright"))
    assert python.environments.uv == local_uv()
    assert local_setups() == {Profile.PYTHON: PythonSetup(local_uv())}
    assert local_fixers() == {Profile.PYTHON: PythonFixer(core_tool("ruff"))}


def test_a_revision_is_the_candidate_when_named(project: GitRepo) -> None:
    project.write("a.txt", "staged\n")
    project.git("add", "a.txt")
    repo, candidate = candidate_of(argparse.Namespace(rev="HEAD"))
    assert repo.worktree == project.path.resolve()
    assert candidate.tree == project.git("rev-parse", "HEAD^{tree}").strip()


def test_the_index_a_hook_selected_is_the_candidate(
    project: GitRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    project.write("b.txt", "second\n")
    alternate = project.path / ".git" / "alternate-index"
    project.git("read-tree", "HEAD", GIT_INDEX_FILE=str(alternate))
    project.git("add", "b.txt", GIT_INDEX_FILE=str(alternate))
    expected = project.git("write-tree", GIT_INDEX_FILE=str(alternate)).strip()
    _, default = candidate_of(argparse.Namespace(rev=None))
    assert default.tree == project.git("rev-parse", "HEAD^{tree}").strip()
    monkeypatch.setenv("GIT_INDEX_FILE", ".git/alternate-index")
    _, candidate = candidate_of(argparse.Namespace(rev=None))
    assert candidate.tree == expected


def test_coverage_is_described_per_component() -> None:
    assert coverage_text(SUMMARIES) == (
        "unit coverage of a: line 75.00% (3/4), branch 50.00% (1/2), "
        "changed lines not applicable (0/0)\n"
        "unit coverage of b: line 100.00% (1/1), branch not measured, "
        "changed lines 100.00% (1/1)\n"
    )
    assert coverage_text(()) == ""


def test_coverage_is_reported_as_json_counters() -> None:
    assert coverage_json(SUMMARIES) == [
        {
            "component": "a",
            "line": {"covered": 3, "total": 4},
            "branch": {"covered": 1, "total": 2},
            "changed": {"covered": 0, "total": 0},
        },
        {
            "component": "b",
            "line": {"covered": 1, "total": 1},
            "branch": None,
            "changed": {"covered": 1, "total": 1},
        },
    ]
    assert coverage_json(()) == []
