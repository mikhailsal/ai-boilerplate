"""Git plumbing: candidate identity, isolated snapshots, and revision line mapping."""

from quality.gitio.candidate import Candidate, index_tree, revision, staged
from quality.gitio.diff import FileChange, Hunk, added_lines, map_line, tree_changes
from quality.gitio.errors import RULES, GitioError
from quality.gitio.history import HistoryBlob, RevisionRange, new_blobs
from quality.gitio.repo import Repository
from quality.gitio.revisions import (
    commit_lines,
    merge_queue_lines,
    pull_request_lines,
    push_lines,
)
from quality.gitio.snapshot import Snapshot, check_isolated, materialize
from quality.gitio.tree import TreeEntry, blob_id, list_tree, read_blobs
from quality.gitio.version import parse_version, version_findings

__all__ = [
    "RULES",
    "Candidate",
    "FileChange",
    "GitioError",
    "HistoryBlob",
    "Hunk",
    "Repository",
    "RevisionRange",
    "Snapshot",
    "TreeEntry",
    "added_lines",
    "blob_id",
    "check_isolated",
    "commit_lines",
    "index_tree",
    "list_tree",
    "map_line",
    "materialize",
    "merge_queue_lines",
    "new_blobs",
    "parse_version",
    "pull_request_lines",
    "push_lines",
    "read_blobs",
    "revision",
    "staged",
    "tree_changes",
    "version_findings",
]
