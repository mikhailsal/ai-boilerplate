# Requirement traceability (R06–R10)

Continuation of the [traceability matrix](traceability.md).

## R06 Unit tests and coverage

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| R06.1 | Per component: line 80%, branch 70%, changed lines 90%, new file nonzero | P04 | `rules/test_coverage.py`, `engine/test_suite_scope.py` | DONE |
| R06.2 | Real line and branch collection in all four profiles; missing driver is an error | P04–P08 | P04: missing branch data fails (`coverage.branch-unmeasured`); Python: `adapters/python/test_runner.py::test_coverage_settings_measure_branches_into_the_output`, `test_config.py::test_the_lockfile_must_lock_the_test_packages`, `acceptance/test_commit.py::test_a05_branch_coverage_fails_despite_full_line_coverage`; other profiles in P06–P08 | IN_PROGRESS |
| R06.3 | Expected source inventory derived independently and reconciled | P04–P08 | P04: `coverage.unaccounted` from snapshot inventory; Python: `adapters/python/test_profile.py::test_only_python_modules_are_expected_in_coverage`, `acceptance/test_commit.py::test_a01_a_new_file_nothing_imports_must_be_covered`; other profiles in P06–P08 | IN_PROGRESS |
| R06.4 | Test bodies excluded; reusable test infrastructure covered as tooling | P04, P05 | P04: test roots excluded, testkit covered as source; P05: `adapters/python/test_runner.py::test_unit_runs_measure_the_source_roots`, the core testkit at 100% in the self-hosted gate | DONE |
| R06.5 | Exact integer comparisons; separate counters; no cross-language averages | P04 | `coverage/test_model.py`, `rules/test_coverage.py` | DONE |
| R06.6 | Integration/e2e coverage never satisfies unit thresholds | P04 | `engine/test_suite_scope.py::test_integration_coverage_never_satisfies_unit_floors` | DONE |
| R06.7 | Evidence: success, expected suite, fresh parseable reports, complete accounting | P04 | `engine/test_suites.py`, parser tests, decision 0008 | DONE |
| R06.8 | `NOT_APPLICABLE` only for proven absence; broken globs fail | P04 | `rules/test_coverage.py` (not applicable, `coverage.no-source`) | DONE |
| R06.9 | Unit tests isolated from services and network; instrumentation loopback only | P04–P08 | Python: fresh home, temporary directory, and allowlisted environment (`adapters/python/test_runner.py`); network isolation is not enforced yet ([decision 0009](../decisions/0009-python-profile.md#residual-risks)); other profiles in P06–P08 | IN_PROGRESS |
| R06.10 | Commit runs full unit suites of affected components and reverse dependencies | P04, P05 | P04: `discovery/test_scope.py`, `engine/test_suite_scope.py`; P05: `acceptance/test_profile_cases.py::test_each_component_is_tested_and_counted_on_its_own`, `acceptance/test_commit.py::test_a10_a_lockfile_change_reruns_the_suites` | DONE |
| R06.11 | No custom result cache; CI reruns; no ratchet, regressions reported | P04, P10 | P04: no result cache or ratchet (decision 0008); regressions and CI in P10 | IN_PROGRESS |

## R07 Tier 1 profile choices

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| R07.1 | Stable compatible versions with primary sources | P00 | Decision 0001 | DONE |
| R07.2 | Python: Ruff, Pyright strict, pytest, coverage.py branches, AST metrics | P05 | `tests/acceptance/test_commit.py`, `test_profile_cases.py`, `tests/unit/adapters/python`, [decision 0009](../decisions/0009-python-profile.md) | DONE |
| R07.3 | TypeScript: Prettier, typed ESLint, strict tsc, Vitest V8 coverage | P06 | TypeScript acceptance suite | TODO |
| R07.4 | TypeScript: .ts/.tsx/.mts/.cts, remapped source, aliases, references, ESM and CJS | P06 | TypeScript acceptance suite | TODO |
| R07.5 | Dart: format, analyze, lints, test, coverage with branches, analyzer helper | P07 | Dart acceptance suite | TODO |
| R07.6 | Dart: multiple packages, workspace directories, VM service lifecycle | P07 | Dart workspace acceptance case | TODO |
| R07.7 | PHP: CS Fixer, PHPStan max, PHPUnit, Xdebug branches, AST metrics | P08 | PHP acceptance suite | TODO |
| R07.8 | PHP: PCOV-only cannot satisfy branches; real report format validated | P08 | Driver failure acceptance cases | TODO |
| R07.9 | Per profile: format, lint/types, structure, unit failure, line, branch, changed line, unimported file, multi-component | P05–P08 | Python: `acceptance/test_commit.py` (format, lint, types, branch, changed line, unimported file) and `test_profile_cases.py` (structure, unit failure, line, multi-component); other profiles in P06–P08 | IN_PROGRESS |

## R08 Required behavioral scenarios

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| R08.1 | Capability axis: library, CLI, HTTP API, database, contracts, queues, UI | P09 | Scenario schema tests | TODO |
| R08.2 | Scenario schema: ID, component, capability, level, test mapping, stage | P09 | Schema validation tests | TODO |
| R08.3 | Obligations resolve to executed passing tests; skips and empty selections fail | P09 | Reconciliation tests | TODO |
| R08.4 | Reusable capability requirements for each capability | P09 | Capability requirement tests | TODO |
| R08.5 | Explicit capability declaration incl. justified none; OpenAPI reconciliation | P09 | Declaration tests | TODO |
| R08.6 | Two reference fixtures: CLI/library and HTTP with a real database | P09 | Fixture acceptance tests | TODO |
| R08.7 | Focused, skipped, and flaky handling with scoped quarantine | P09 | Quarantine tests | TODO |
| R08.8 | Optional mutation, property, and performance profile contracts | P09 | Enhanced profile tests | TODO |

## R09 CI and trust boundary

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| R09.1 | CLI decides; CI wrappers translate, install, invoke, publish | P10 | Workflow review and tests | TODO |
| R09.2 | JSON diagnostics, native coverage, JUnit/LCOV/Cobertura exports, relative paths | P04, P10 | P04: native report parsers with repository-relative paths; exports in P10 | IN_PROGRESS |
| R09.3 | GitHub Actions workflow and GitLab reference wrapper using the same entry points | P10 | actionlint and wrapper tests | TODO |
| R09.4 | Generic execution without provider variables; live runs reported separately | P10 | Plain Linux gate test | TODO |
| R09.5 | Aggregate job fails on failed, cancelled, skipped, or missing jobs | P10 | Aggregation tests | TODO |
| R09.6 | Protection guidance and CODEOWNERS for control files incl. CODEOWNERS | P10 | Control-file tests | TODO |
| R09.7 | No privileged untrusted execution; pinned actions; minimal permissions | P10 | Workflow lint tests | TODO |
| R09.8 | Honest trust boundary documented | P10, P11 | docs/trust-boundary.md | TODO |

## R10 Template lifecycle and evidence

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| R10.1 | Fresh copy: bootstrap, discovery, checks, add component without engine edits | P11 | Template lifecycle acceptance | TODO |
| R10.2 | Repeated bootstrap preserves user content and hooks; conflicts non-destructive | P05, P11 | `acceptance/test_bootstrap.py`, `hooks/test_install.py`; fresh template copy in P11 | IN_PROGRESS |
| R10.3 | Extension guide and adapter contract tests; unsupported source fails | P11 | Contract tests | TODO |
| R10.4 | Copied projects update policy and tools through reviewable changes | P11 | docs/maintenance.md | TODO |
| R10.5 | Invalid fixtures as templates or generated; runtime secrets and large blobs | All | Fixture layout | TODO |
| R10.6 | Regression test for every gate defect found during implementation | All | Phase records; P05: `acceptance/test_commit.py::test_modules_named_like_configuration_are_checked_as_source`, `discovery/test_manifests.py`, `engine/test_fixes.py::test_a_fixer_that_cannot_run_is_reported_and_not_counted` | IN_PROGRESS |
| R10.7 | Bounded summaries with commands, versions, exit codes, commit references | All | Phase records | TODO |
