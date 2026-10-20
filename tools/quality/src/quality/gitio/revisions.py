"""Which lines of a tested tree are new for commit, push, pull-request, and queue checks.

See decision 0004. Lines are reported per path of the tested tree.
"""

from __future__ import annotations

import re

from quality.gitio.candidate import Candidate
from quality.gitio.diff import LineSet, added_lines, carry_lines
from quality.gitio.errors import GIT_REVISION_UNRESOLVABLE, GitioError
from quality.gitio.repo import Repository

ZERO_REVISION = re.compile(r"^0+$")


def commit_lines(repo: Repository, candidate: Candidate) -> LineSet:
    """Lines added by a commit candidate relative to its base tree (HEAD or empty)."""
    return added_lines(repo, candidate.base_tree, candidate.tree)


def push_lines(repo: Repository, before: str, after: str) -> LineSet:
    """Lines added by a push; an all-zero `before` means a new branch with no base."""
    old_tree = (
        repo.empty_tree()
        if ZERO_REVISION.match(before)
        else repo.tree_of(repo.resolve_commit(before))
    )
    return added_lines(repo, old_tree, repo.tree_of(repo.resolve_commit(after)))


def merge_queue_lines(repo: Repository, base: str, tested: str) -> LineSet:
    """Lines a merge-queue entry adds on top of the base branch."""
    return added_lines(
        repo,
        repo.tree_of(repo.resolve_commit(base)),
        repo.tree_of(repo.resolve_commit(tested)),
    )


def pull_request_lines(repo: Repository, base: str, head: str, tested: str) -> LineSet:
    """Lines the pull request contributes to the tested tree.

    Lines added between the merge base and the head are carried into the tested
    tree. Lines that differ from both the base and the head in the tested tree
    (conflict resolutions) are added. Lines that came unchanged from the base
    branch are never included.
    """
    base_commit = repo.resolve_commit(base)
    head_commit = repo.resolve_commit(head)
    tested_commit = repo.resolve_commit(tested)
    if not repo.is_ancestor(head_commit, tested_commit):
        message = f"tested revision '{tested}' does not contain head '{head}'"
        raise GitioError(GIT_REVISION_UNRESOLVABLE.diagnostic(message))
    merge_base = repo.merge_base(base_commit, head_commit)
    base_tree, head_tree = repo.tree_of(base_commit), repo.tree_of(head_commit)
    tested_tree = repo.tree_of(tested_commit)
    contributed = carry_lines(
        repo, added_lines(repo, repo.tree_of(merge_base), head_tree), head_tree, tested_tree
    )
    from_base = added_lines(repo, base_tree, tested_tree)
    from_head = added_lines(repo, head_tree, tested_tree)
    result = dict(contributed)
    for path, numbers in from_base.items():
        resolved = numbers & from_head.get(path, frozenset())
        if resolved:
            result[path] = result.get(path, frozenset()) | resolved
    return result
