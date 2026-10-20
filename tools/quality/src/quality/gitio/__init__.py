"""Git plumbing: candidate identity, isolated snapshots, and revision line mapping."""

from quality.gitio.candidate import Candidate, index_tree, revision, staged
from quality.gitio.diff import FileChange, Hunk, added_lines, map_line, tree_changes
from quality.gitio.errors import RULES, GitioError
from quality.gitio.repo import Repository
from quality.gitio.revisions import (
    commit_lines,
    merge_queue_lines,
    pull_request_lines,
    push_lines,
)
from quality.gitio.snapshot import Snapshot, check_isolated, materialize
from quality.gitio.tree import TreeEntry, list_tree, read_blobs

__all__ = [
    "RULES",
    "Candidate",
    "FileChange",
    "GitioError",
    "Hunk",
    "Repository",
    "Snapshot",
    "TreeEntry",
    "added_lines",
    "check_isolated",
    "commit_lines",
    "index_tree",
    "list_tree",
    "map_line",
    "materialize",
    "merge_queue_lines",
    "pull_request_lines",
    "push_lines",
    "read_blobs",
    "revision",
    "staged",
    "tree_changes",
]
