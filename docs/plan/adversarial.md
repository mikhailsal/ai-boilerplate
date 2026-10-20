# Adversarial acceptance checklist

Each negative case has a passing control case. Items are integrated into the
listed phases and rerun in P12. A box is checked only after the P12 rerun.

| Done | ID | Case | Phases | Proof |
| --- | --- | --- | --- | --- |
| [ ] | A01 | New unimported executable file is counted and blocked when uncovered, per Tier 1 language | P05–P08 | TODO |
| [ ] | A02 | A covered component cannot compensate for an uncovered sibling | P04–P08 | P04: `engine/test_suite_scope.py::test_a_covered_component_cannot_cover_for_its_sibling`; per profile in P05–P08 |
| [ ] | A03 | Integration/e2e coverage does not repair insufficient unit coverage | P04 | P04: `engine/test_suite_scope.py::test_integration_coverage_never_satisfies_unit_floors` |
| [ ] | A04 | Changed-line failure blocks even when component totals pass | P04–P08 | P04: `engine/test_suite_scope.py::test_uncovered_changed_lines_fail_although_totals_pass`; per profile in P05–P08 |
| [ ] | A05 | Native branch failure blocks independently of line coverage, all four profiles | P05–P08 | TODO |
| [ ] | A06 | Staged source with only an unstaged or untracked covering test is rejected | P02, P05 | P02: the covering test is absent from the snapshot (`test_only_staged_content_is_tested`); gate rejection in P05 |
| [ ] | A07 | Bad staged test not rescued by unstaged fix; good staged tree not penalized by bad worktree | P02, P05 | P02: snapshot holds staged content only (`test_only_staged_content_is_tested`); gate outcome in P05 |
| [ ] | A08 | Old reports, missing drivers, missing runners, zero unexpected tests, malformed outputs fail | P04–P08 | P04: `engine/test_suites.py::test_reports_that_are_not_fresh_evidence_of_this_run_fail`, `test_a_unit_run_without_executed_tests_fails`, `test_a_component_without_a_runner_is_unavailable`, parser tests; drivers in P05–P08 |
| [ ] | A09 | Exact threshold edges incl. just-below minima and very small diffs | P04 | P04: `coverage/test_model.py::test_minima_are_compared_exactly`, `rules/test_coverage.py::test_just_below_a_floor_fails`, `test_a_one_line_change_is_measured` |
| [ ] | A10 | Deleting tests or changing tool/config/lockfile inputs triggers the rerun | P04, P05 | P04: `engine/test_suite_scope.py::test_only_affected_components_are_tested`; hook rerun in P05 |
| [ ] | A11 | Unknown source, missing profiles, skipped checks, incomplete matrix jobs cannot pass | P02, P10 | P02: unknown, unowned, and unsupported files fail discovery (`test_classify.py`, `test_inventory.py`); CI jobs in P10 |
| [ ] | A12 | Secret or large blob added and removed before the tip is detected in new history | P03, P10 | P03: `engine/test_history.py::test_secrets_and_large_blobs_deleted_before_the_tip_fail`; merge gate in P10 |
| [ ] | A13 | Scenarios not satisfied by skips, expected failures, empty selections, stale results | P09 | TODO |
| [ ] | A14 | Bootstrap and hooks preserve user changes and never auto-stage fixes | P05 | TODO |
| [ ] | A15 | The engine and native helpers are tested and covered | P05–P08 | TODO |
| [ ] | A16 | A clean valid four-language repository passes | P11 | TODO |
