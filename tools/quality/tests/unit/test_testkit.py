from pathlib import Path

import pytest

from quality.testkit.gitrepo import GitCommandError, GitRepo
from quality.testkit.policies import ComponentSpec, build_policy, classification_toml


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
