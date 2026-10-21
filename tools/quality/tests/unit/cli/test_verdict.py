import argparse
from pathlib import Path

import pytest

from quality.cli.verdict import candidate_of, coverage_json, coverage_text
from quality.coverage import Counter
from quality.rules.coverage import ComponentCoverage
from quality.testkit.gitrepo import GitRepo

SUMMARIES = (
    ComponentCoverage("a", Counter(3, 4), Counter(1, 2), Counter(0, 0)),
    ComponentCoverage("b", Counter(1, 1), None, Counter(1, 1)),
)


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
