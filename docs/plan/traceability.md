# Requirement traceability (R01–R05)

Every mandatory requirement of the external assignment has an owner phase and
a planned proof. The `Proof` column names tests or documents once they exist.
Continued in [R06–R10](traceability-r06-r10.md) and the
[adversarial checklist](adversarial.md).

Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`.

## R01 Scope and implementation quality

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| R01.1 | Tier 1 profiles: Dart VM, Python, TypeScript on Node, PHP | P05–P08 | Per-profile acceptance suites | TODO |
| R01.2 | Flutter/web detected separately and reported unsupported | P07 | Discovery acceptance case | TODO |
| R01.3 | Small typed Python core, uv-locked, native tools reused | P01 | `tools/quality/uv.lock`, Pyright strict config, [P01](phases/P01.md) | DONE |
| R01.4 | Application, tooling core, and dormant helper roles; activation rules | P02, P11 | `tests/unit/discovery/test_activation.py`; template tests in P11 | IN_PROGRESS |
| R01.5 | Separate policy, snapshot, discovery, process, adapters, reports, CI | P01–P04 | Declared module architecture rule on the core | IN_PROGRESS |
| R01.6 | No new package manager, build system, parser, or test framework | All | Architecture decision 0003 | TODO |
| R01.7 | Own code, helpers, and adapters pass rules and coverage | P05–P08 | Self-hosted gate on every commit | TODO |
| R01.8 | Mocked unit tests plus real-tool acceptance tests | P04–P08 | Unit and acceptance suites | TODO |
| R01.9 | Maintainer acceptance separate from application validation | P05, P11 | Exported sample repositories | TODO |

## R02 Reproducibility and interface

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| R02.1 | Public operations: bootstrap, doctor, check, test, gate, fix, explain, self-test, component add, tools update | P01, P05, P10, P11 | CLI tests and docs/cli.md | IN_PROGRESS |
| R02.2 | One schema-validated policy; derived configs generated or verified | P01, P03 | `tests/unit/policy`, `policy schema --check` | IN_PROGRESS |
| R02.3 | Unknown keys, invalid values, conflicting roots, invalid exceptions detected | P01, P03 | `tests/unit/policy/test_load.py`, `test_validate.py` | IN_PROGRESS |
| R02.4 | Pinned versions, lockfiles, checksums; clean-environment proof | P00, P05, P11 | Decision 0001, clean container run | TODO |
| R02.5 | Install only active-profile tools; honest prerequisites | P05, P11 | Bootstrap tests, decision 0002 | TODO |
| R02.6 | Check-only hooks and CI; no auto-staging; no floating fetches | P05 | Hook tests | TODO |

## R03 Git inventory and snapshots

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| R03.1 | Candidate files from Git incl. additions, deletions, renames, `GIT_INDEX_FILE` | P02 | `tests/unit/gitio/test_candidate.py`, `test_diff.py`, `tests/unit/cli/test_inventory_cmd.py` | DONE |
| R03.2 | Components from manifests and explicit declarations; types by name, extension, shebang | P02 | `tests/unit/discovery/test_filetypes.py`, `test_manifests.py`, `test_inventory.py`, decision 0006 | DONE |
| R03.3 | Categories; ambiguous or unsupported source fails; unknown assets need classification | P02 | `tests/unit/discovery/test_classify.py`, `test_inventory.py` | DONE |
| R03.4 | Isolated candidate tree; worktree, untracked, stale data excluded; index preserved | P02 | `tests/unit/gitio/test_snapshot.py::test_only_staged_content_is_tested` | DONE |
| R03.5 | Candidate identity rechecked before success | P02 | `tests/unit/gitio/test_candidate.py::test_concurrent_index_changes_are_detected`; gate call in P05 | DONE |
| R03.6 | First commit, alternate index, detached HEAD, unusual paths, exec bits, deletions | P02 | `tests/unit/gitio/test_candidate.py`, `test_tree.py`, `test_snapshot.py` | DONE |
| R03.7 | Symlinks, submodules, LFS handled safely or rejected explicitly | P02 | `tests/unit/gitio/test_snapshot.py`, `tests/unit/discovery/test_inventory.py` | DONE |
| R03.8 | No escape via source links, config, ambient paths, or inherited Git variables | P02, P05–P08 | `tests/unit/gitio/test_repo.py`, `test_snapshot.py`; profile proofs in P05–P08 | IN_PROGRESS |
| R03.9 | Commit diff: index vs HEAD (empty tree first); amend and merge modes; unmerged index rejected | P02, P04 | `tests/unit/gitio/test_revisions.py`, `test_candidate.py`; coverage use in P04 | IN_PROGRESS |
| R03.10 | PR/merge: base, source head, tested snapshot; merge base; reconciled lines; merge queue | P02, P10 | `tests/unit/gitio/test_revisions.py`; CI arguments in P10 | IN_PROGRESS |
| R03.11 | Missing history or unresolvable mapping fails | P02, P10 | `tests/unit/gitio/test_revisions.py::test_missing_history_fails`; shallow clones in P10 | IN_PROGRESS |

## R04 Common code and repository policy

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| R04.1 | Default thresholds retained in the delivered template | P03 | Policy defaults test | TODO |
| R04.2 | Real AST metrics with exact counting rules per language | P03, P06–P08 | Metric unit and helper tests | TODO |
| R04.3 | One formatter per file set; explicit lint selection; category policy | P03, P05–P08 | Profile configs and tests | TODO |
| R04.4 | Pinned secret scanner over candidate and new history; redacted output | P03, P10 | Synthetic secret history tests | TODO |
| R04.5 | Blob limit over candidate and all new Git objects; asset/LFS statement | P03, P10 | Large blob history tests | TODO |
| R04.6 | Lockfile validation and dependency audit in merge CI; severity policy | P10 | Audit tests with clean and failing controls | TODO |
| R04.7 | Declared module boundaries: forbidden edges and cycles | P03, P06–P08 | Architecture rule tests | TODO |

## R05 Documentation and instructions

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| R05.1 | Markdown lint, docs index, internal paths and anchors (case-sensitive) | P03 | Docs rule tests | TODO |
| R05.2 | External URLs checked separately with timeouts | P03 | External link tests | TODO |
| R05.3 | Concise root AGENTS.md; thresholds stored once and linked | P03, P11 | AGENTS.md limit rule | TODO |
| R05.4 | English policy with advisory detection; no ASCII-only rule | P03 | Advisory tests | TODO |
| R05.5 | Documented command entry points verified against the CLI | P03 | Command reference rule tests | TODO |
| R05.6 | Exceptions: rule ID, exact scope, reason, owner, expiry; unused and expired detected | P03 | Exception tests | TODO |
| R05.7 | Generated/vendor classification is not a universal exemption | P03 | Classification tests | TODO |
