import pytest

from quality.gitio import (
    GitioError,
    commit_lines,
    merge_queue_lines,
    pull_request_lines,
    push_lines,
    staged,
)
from quality.testkit.gitrepo import GitRepo

BASE = "".join(f"line {n}\n" for n in range(1, 11))


def edit(text: str, number: int, replacement: str) -> str:
    rows = text.splitlines(keepends=True)
    rows[number - 1] = replacement + "\n"
    return "".join(rows)


def test_commit_lines_compare_the_index_with_head(repo: GitRepo) -> None:
    repo.write("a.py", "one\ntwo\n")
    repo.git("add", "a.py")
    git = repo.repository()
    assert commit_lines(git, staged(git)) == {"a.py": frozenset({1, 2})}
    repo.commit_all("first")
    repo.write("a.py", "one\nTWO\nthree\n")
    repo.git("add", "a.py")
    assert commit_lines(git, staged(git)) == {"a.py": frozenset({2, 3})}


def test_push_lines_treat_a_zero_revision_as_a_new_branch(repo: GitRepo) -> None:
    repo.write("a.py", "one\n")
    first = repo.commit_all("first")
    repo.write("a.py", "one\ntwo\n")
    second = repo.commit_all("second")
    git = repo.repository()
    assert push_lines(git, "0" * 40, second) == {"a.py": frozenset({1, 2})}
    assert push_lines(git, first, second) == {"a.py": frozenset({2})}


def pull_request(repo: GitRepo) -> tuple[str, str, str]:
    """Build a PR whose base branch moved on after the PR branched off."""
    repo.write("shared.py", BASE)
    repo.commit_all("base")
    repo.git("checkout", "-q", "-b", "feature")
    repo.write("shared.py", edit(BASE, 2, "feature change"))
    repo.write("feature.py", "f1\nf2\n")
    head = repo.commit_all("feature")
    repo.git("checkout", "-q", "main")
    repo.write("shared.py", edit(BASE, 9, "main change"))
    repo.write("main_only.py", "m1\n")
    base = repo.commit_all("main moves on")
    repo.git("merge", "-q", "--no-ff", "-m", "merge feature", "feature")
    return base, head, repo.head()


def test_pull_request_lines_exclude_changes_from_the_base_branch(repo: GitRepo) -> None:
    base, head, tested = pull_request(repo)
    assert pull_request_lines(repo.repository(), base, head, tested) == {
        "shared.py": frozenset({2}),
        "feature.py": frozenset({1, 2}),
    }


def test_pull_request_lines_without_a_merge_use_the_head(repo: GitRepo) -> None:
    base, head, _ = pull_request(repo)
    assert pull_request_lines(repo.repository(), base, head, head) == {
        "shared.py": frozenset({2}),
        "feature.py": frozenset({1, 2}),
    }


def test_conflict_resolutions_belong_to_the_pull_request(repo: GitRepo) -> None:
    repo.write("shared.py", BASE)
    repo.commit_all("base")
    repo.git("checkout", "-q", "-b", "feature")
    repo.write("shared.py", edit(BASE, 5, "feature version"))
    head = repo.commit_all("feature")
    repo.git("checkout", "-q", "main")
    repo.write("shared.py", edit(BASE, 5, "main version"))
    base = repo.commit_all("main")
    assert not repo.run_git("merge", "-q", "feature").ok
    repo.write("shared.py", edit(BASE, 5, "resolved version"))
    tested = repo.commit_all("resolve")
    assert pull_request_lines(repo.repository(), base, head, tested) == {
        "shared.py": frozenset({5})
    }


def test_merge_queue_lines_compare_with_the_base(repo: GitRepo) -> None:
    base, _, tested = pull_request(repo)
    assert merge_queue_lines(repo.repository(), base, tested) == {
        "shared.py": frozenset({2}),
        "feature.py": frozenset({1, 2}),
    }


def test_tested_revision_must_contain_the_head(repo: GitRepo) -> None:
    base, head, _ = pull_request(repo)
    with pytest.raises(GitioError, match="does not contain head") as raised:
        pull_request_lines(repo.repository(), base, head, base)
    assert raised.value.diagnostic.rule == "git.revision-unresolvable"


def test_missing_history_fails(repo: GitRepo) -> None:
    base, _, _ = pull_request(repo)
    repo.git("checkout", "-q", "--orphan", "unrelated")
    unrelated = repo.commit_all("unrelated")
    git = repo.repository()
    with pytest.raises(GitioError, match="no merge base"):
        pull_request_lines(git, base, unrelated, unrelated)
    with pytest.raises(GitioError, match="no such commit"):
        pull_request_lines(git, "f" * 40, unrelated, unrelated)
