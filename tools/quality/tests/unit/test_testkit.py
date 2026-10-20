from pathlib import Path

import pytest

from quality.process import Completed
from quality.testkit.gitrepo import GitCommandError, GitRepo
from quality.testkit.policies import ComponentSpec, build_policy, classification_toml
from quality.testkit.scratch import (
    CORE_SOURCE,
    component,
    create_project,
    output,
    rules_of,
    shared_caches,
)


def test_failed_arrangement_commands_fail_the_test(tmp_path: Path) -> None:
    repo = GitRepo.create(tmp_path / "repo")
    with pytest.raises(GitCommandError, match="git no-such-command failed"):
        repo.git("no-such-command")


def test_repositories_use_an_isolated_home(tmp_path: Path) -> None:
    repo = GitRepo.create(tmp_path / "repo")
    assert repo.environ()["HOME"] == str(tmp_path / "repo-home")
    assert repo.run_git("config", "--global", "--list").stdout == b""


def test_build_policy_rejects_invalid_documents() -> None:
    with pytest.raises(AssertionError, match="invalid test policy"):
        build_policy(ComponentSpec(id="Not Valid"))


def test_build_policy_renders_classifications() -> None:
    policy = build_policy(extra=classification_toml("vendor/**", "vendor"))
    assert [(c.pattern, c.category.value) for c in policy.classification] == [
        ("vendor/**", "vendor")
    ]


def test_scratch_projects_run_the_core_under_test(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", component("lib"))
    assert (project.path / "lib" / "uv.lock").is_file()
    assert project.repo.git("status", "--porcelain") == ""
    result = project.quality("--help")
    assert result.returncode == 0
    assert "usage: quality" in output(result)
    assert project.environ()["XDG_CACHE_HOME"]


def test_scratch_projects_can_embed_the_core(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", core=True)
    core = project.path / "tools" / "quality"
    assert (core / "src/quality/cli/main.py").read_bytes() == (
        CORE_SOURCE / "quality/cli/main.py"
    ).read_bytes()
    assert not list(core.rglob("__pycache__"))
    for name in ("uv.lock", "toolchains.toml"):
        assert (core / name).read_bytes() == (CORE_SOURCE.parent / name).read_bytes()
    assert (
        'pattern = "tools/quality/**"\ncategory = "vendor"'
        in (project.path / "quality.toml").read_text()
    )
    assert str(core / "src") in (project.path / "quality").read_text()
    assert project.repo.git("status", "--porcelain") == ""
    assert "usage: quality" in output(project.quality("--help"))


def test_scratch_commits_stage_the_named_paths_or_everything(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project")
    first = project.head()
    project.write("notes.txt", "one\n")
    project.write("other.txt", "two\n")
    assert project.commit("notes", "notes.txt").ok
    assert project.repo.git("status", "--porcelain") == "?? other.txt\n"
    assert project.commit("the rest").ok
    assert project.head() != first
    assert project.index_tree() == project.repo.git("rev-parse", "HEAD^{tree}").strip()
    assert project.hook("pre-commit") == project.path / ".git" / "hooks" / "pre-commit"


def test_rules_are_read_from_rendered_findings() -> None:
    text = b"a.py:1: error: bad (python.lint) [app]\nerror: low (coverage.line)\n(x) not (a rule)\n"
    result = Completed(("quality",), 1, text, b"error: env (git.failed)\n", 0.0)
    assert rules_of(result) == {"python.lint", "coverage.line", "git.failed"}


def test_scratch_users_share_the_caller_caches() -> None:
    assert shared_caches({"HOME": "/home/u"}) == {"XDG_CACHE_HOME": "/home/u/.cache"}
    environ = {"HOME": "/home/u", "XDG_CACHE_HOME": "/c", "UV_CACHE_DIR": "/uv"}
    assert shared_caches(environ) == {"XDG_CACHE_HOME": "/c", "UV_CACHE_DIR": "/uv"}
