# 0004 Candidate snapshots and revision semantics

Status: accepted (P00); amended in P02.

## Candidate identity

- Commit stage: the candidate is the index named by `GIT_INDEX_FILE` (or the
  default index). The core copies that file and runs `git write-tree` on the
  copy, so the original index is never rewritten. Like `git commit`, this may
  add unreferenced tree objects to the object database; refs, the index, and
  the work tree are unchanged. Unmerged entries (`git ls-files -u`) reject the
  commit before any other check.
- Merge stage and `--head`: the candidate is the tree of a resolved revision.
- The candidate identity is the tree object ID. Before returning success the
  core recomputes it from the original source; a difference fails with
  `git.candidate-changed`, so a concurrent edit cannot reuse a result.

## Materialization

The snapshot is written to a fresh temporary directory from `git ls-tree -r -z`
and `git cat-file --batch`, which yields exact blob bytes without clean,
smudge, or end-of-line filters:

- `100644` and `100755` become files with the matching executable bit;
- `120000` symlinks must have relative targets; after writing, every link is
  resolved with `realpath`, including chains through other links, and must
  stay inside the snapshot, otherwise `git.symlink-escape` fails the run;
- `160000` gitlinks (submodules) become empty directories; discovery rejects
  them with `discovery.submodule-unsupported` unless they are classified as
  vendor content ([decision 0006](0006-discovery-and-classification.md));
- Git LFS pointer files are materialized as pointers. Pointer text is checked;
  object content is not inspected, which the asset policy states explicitly.

Unstaged edits, untracked files, ignored files, and old reports therefore
cannot influence the result. Native tools search parent directories for
configuration, so the snapshot's parent directories must not contain project
markers such as `quality.toml`, `pyproject.toml`, `conftest.py`,
`package.json`, `node_modules`, `pubspec.yaml`, or `composer.json`; one
found there fails with `git.snapshot-not-isolated`.

Paths with spaces, newlines, or non-UTF-8 bytes are handled as bytes from the
`-z` output.

## Validator provenance

Policy, native configuration, and tests come from the snapshot. The launcher
runs the core from `tools/quality/src` inside the snapshot using the locked
environment, so unstaged edits to the validator do not affect the decision.
A candidate whose core lockfile differs from the installed environment fails
with an instruction to run the bootstrap command (P05).

## Environment sanitation

Child processes receive an allowlisted environment. `GIT_*`, `PYTHONPATH`,
`NODE_PATH`, `NODE_OPTIONS`, `PHP_INI_SCAN_DIR`, and similar variables are
removed; the alternate index is translated into a tree ID deliberately and is
never propagated to tests that create their own repositories. Explicit values
(for example the component import roots) are set by the adapter.

## Commit diff

Changed lines for commit validation are the added lines of
`git diff -M <HEAD tree or empty tree> <candidate tree>`. The same comparison
applies to `git commit --amend` (lines changed relative to the commit being
replaced) and to merge commits (lines changed relative to the first parent).

## Merge and pull request revisions

Three revisions are explicit: base `B`, source head `H`, tested snapshot `T`
(defaults to `H`). With `M = merge-base(B, H)`:

- PR-new lines in `T` = lines added by `M..H`, mapped into `T` through
  `diff H T`, plus lines added in both `diff B T` and `diff H T` (conflict
  resolutions).
- Lines that `T` received unchanged from `B` are never PR-new.
- Merge queue (`T` built on `B` from one entry): PR-new lines = added lines of
  `diff B T`.
- Push to a branch: `B` is the previous tip, `H = T` is the new tip; the zero
  revision means an empty tree base.

Missing objects, a shallow history without the merge base, or a `T` that does
not contain `H` fail with `git.revision-unresolvable`; no gate is skipped.

## History range checks

Secret scanning and the blob size limit cover every commit and blob reachable
from `T` but not from `B` (`git rev-list --objects B..T`), so content added and
removed before the tip is still found.
