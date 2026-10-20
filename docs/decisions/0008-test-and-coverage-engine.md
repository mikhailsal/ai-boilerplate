# 0008 Test and coverage engine

Status: accepted (P04).

## Scope

The test engine runs the test suites of the components a candidate affects
and enforces the unit coverage floors of [`quality.toml`](../../quality.toml)
separately for each component. Profiles plug in a runner with three
operations: which source files it must account for, how to run one suite, and
how to parse its native coverage report. The Python runner
([decision 0009](0009-python-profile.md)) and `quality test` arrived in P05;
the other profiles follow in P06–P08. Native measurement semantics are
described in [decision 0005](0005-coverage-measurement.md).

## Which components run

A commit candidate is compared with its base tree
([decision 0004](0004-candidate-snapshots.md)), and every changed path counts,
including both sides of a rename.

- A path inside a component affects that component: sources, tests, deleted
  tests, configuration, and lockfiles under its root.
- Components that list an affected component in `depends_on` are affected
  too, transitively.
- The policy file, anything under `tools/quality`, and any other path outside
  every component affect every component, because their effect on tests
  cannot be bounded. Documentation outside components affects none.
- Only active components run
  ([decision 0003](0003-architecture.md)). CI can request every active
  component regardless of changes.

Each selected component runs its full unit suite; tests are never chosen from
the diff. There is no result cache: a suite runs again every time it is
required, and CI reruns everything independently.

## Evidence

Each suite run gets a new empty output directory in the snapshot's work area.
The runner reports where it wrote JUnit results and, for unit suites, the
coverage report. The engine accepts a report only if it is:

- a regular file (not a symbolic link) inside that output directory;
- not older than the directory, allowing 2 seconds for coarse file system
  timestamps;
- within the size limit of the bounded readers, and parseable;
- internally consistent: declared counts and totals must match the records.

A run passes only if the runner exits with status 0, at least one test
executed, and no test failed or raised an error. Skipped tests warn and do not
count as executed. Coverage is parsed only after a clean unit run, so a failed
runner that still wrote a perfect report fails. Integration, contract,
end-to-end, and acceptance suites never feed the unit floors; their coverage
is not read at all.

A component without unit test roots fails with `tests.none`. A runner that
cannot start reports `tools.failed`, and a profile without a runner reports
`profiles.unavailable`. Untrustworthy evidence reports `tests.evidence`.

## Expected sources

The files a component's coverage must account for come from the candidate
snapshot, never from what the tests imported. They are the component's files
in its source roots, of category source, that the profile measures (for
Python, `.py` files). Test roots are excluded. Generated or vendor code is
excluded only through an explicit classification with a reason
([decision 0006](0006-discovery-and-classification.md)).

An expected file missing from the report fails with `coverage.unaccounted`.
Report entries that are not expected sources, such as test files or another
component's files, are ignored, so one component's run can never cover for
another.

## Floors

All comparisons use integers: `covered * 100 >= minimum * total`.
Percentages are shown truncated to two decimals and are never compared. Line
and branch counters stay separate, and nothing is averaged across files,
components, or languages.

| Rule | Counter |
| --- | --- |
| `coverage.line` | Covered executable lines of all expected sources |
| `coverage.branch` | Taken native branch opportunities of all expected sources |
| `coverage.changed-lines` | Covered lines among the executable lines the candidate adds or changes |
| `coverage.new-file` | A new source file with executable lines must have one covered line |

A new file is a path the candidate adds, or one that replaces a non-file such
as a symbolic link. Changed lines that are not executable, such as comments,
are not counted. The changed-line finding lists the uncovered lines.

## Not applicable

A counter of `0/0` is not applicable and reported as `coverage.not-applicable`
information. That holds only when absence is proven: a component without
expected source files is not applicable only if every declared source root
has tracked files. Otherwise the root is broken and `coverage.no-source`
fails. A report without branch measurement fails with
`coverage.branch-unmeasured`; it is never treated as zero branches.

## Report formats

| Format | Writers | Cross-checks |
| --- | --- | --- |
| coverage.py JSON, format 3 | Python | Per-file summaries and totals against the listed lines and arcs |
| LCOV | Vitest, Dart `coverage`, coverage.py | `LF`, `LH`, `BRF`, `BRH` when present; repeated `SF` blocks merge |
| Clover XML | PHPUnit | File statement metrics against the `stmt` lines |
| JUnit XML | pytest, Vitest, PHPUnit | Declared tests, failures, errors, skipped on every suite |

File names in reports are resolved against the directory where the tool ran
and must lie inside the snapshot. LCOV cannot say whether branch collection
was on, so the runner that enabled it states it. pytest reports a teardown
error as a second test case with the same name. It counts once more in the
failure message, which does not change the verdict.

## Exceptions and regressions

`tests.*` and `coverage.*` findings cannot be excepted. The floors change only
in `quality.toml`, and then for every component. There is no ratchet that
forbids coverage from decreasing; regression reports are part of P10.

## Residual risks

- Tests execute candidate code with the user's permissions. A malicious test
  run can write a forged report into its own output directory, and the engine
  cannot tell it from a real one. Code review of test and runner
  configuration and the independent CI run are the mitigation.
- The timestamp check only rejects copies that keep an old modification time.
- Full execution coverage does not prove that all behavior is tested.
