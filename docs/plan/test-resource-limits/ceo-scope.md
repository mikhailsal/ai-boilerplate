# Scope and review: test resource limits

Autoplan: 2026-11-01, SELECTIVE EXPANSION. CEO, DX and engineering primary
reviews completed with concerns; design review skipped because there is no UI.
The owner D4 amendment received affected engineering re-review on 2026-11-06;
the owner approved the final plan on 2026-11-06. [RL00a](rl00a-remote-evidence.md)
is technically complete within its recorded limits; RL00b and RL00c ran in part
on 2026-11-09 and ended in a [no-go recommendation](rl00bc-recommendation.md).
Source: [amended design](../test-resource-limits.md).

## Retained scope and complexity

The owner clarified the goal: reject hungry tests against their own stable
budgets before suite growth exposes accumulated debt. CASE-01 is a required
correction, not an optional report. Preserve every supported profile, nested
budgets, cleanup, coverage, evidence integrity and fail-closed memory protection.
Reuse process supervision, suite selection, policy validation, candidate
snapshots, browser ownership, reports and export fences. Preserve layer direction.

The earlier estimate of 34 implementation paths is superseded by an engineering
impact inventory of 47 named touchpoints: 41 existing and six proposed. This
excludes still-unenumerated test edits and is not a final changed-file count.
Use coherent vertical phases; a new generic orchestration service is unnecessary.

## Scope decisions

| ID | User outcome | Reviewed disposition |
| --- | --- | --- |
| HOST-01 | Separate test quality from host capacity | Cross-project cap withdrawn after owner clarification; no scheduler or shared cap |
| CASE-01 | Catch costly tests while suites are small | Mandatory case time/memory outcome; method and feasibility pending |
| PREVIEW-01 | Inspect effective limits before running | Owner accepted inclusion under D1; same candidate/policy resolver, read-only |
| PROGRESS-01 | Understand a quiet run | Include optional bounded stderr progress; JSON stdout stays clean |
| SLOW-01 | Locate expensive suites | Include optional duration ranking from current-run evidence only |
| MEMORY-01 | Locate memory-heavy suites | Include optional ranking with exact/sampled/unavailable kinds distinguished |
| REPRO-01 | Reproduce the protected failure | Include argument-safe hints using supported quality selectors; no unbounded native certification |

These additions reuse required measurements and CLI surfaces. They do not imply
a hosted dashboard, historical storage, resource-verdict cache or a historical
regression ratchet. No accepted expansion was deferred to TODOS.md. HOST-01
was withdrawn by the reviewer; no owner Add/Defer/Skip answer is fabricated.

## Review coverage and limits

Outside reviews used Claude Code with reported model `claude-opus-5-5`.
Native reviews were independent in-host subagents. Counts describe feedback,
not unique defects or successful live experiments.

| Phase | Primary review | Native voice | Outside voice | Consensus |
| --- | --- | --- | --- | --- |
| CEO | All applicable sections, SELECTIVE EXPANSION | Completed, four issues | Ten concerns read; structured completion unverified after formatting repair | N/A; no formal outside completion credit |
| Design | Skipped: no UI | Skipped | Skipped | N/A |
| DX | Eight dimensions; specification score 5.4 to 7.6/10 | Completed, ten issues | Completed, 17 findings | Six of six areas agree on gaps; exit-code alternative remains D3 |
| Engineering, initial | Four sections; 27 findings including 20 proof families | Completed, seven issues | Completed, 17 findings | Five of six areas agree; original input only |
| Engineering, owner amendment | Four sections; 12 findings/proof gaps; 25 detailed proof cards | Completed, one medium issue | Completed, 14 findings | Five of six concern areas agree; no live feasibility claim |

The CEO spec checkpoint was reviewed twice: one inconsistency fixed, final
assessment 9/10. DX scores assess the amended specification, not observed
onboarding. Time to first understood protected result is unknown. Both native
and outside engineering voices identified evidence/attribution gaps; re-review
added scope-bound verification, charged-memory/profile preregistration and
checker-capacity reporting while preserving known own timeout violations. Retaining hostile same-UID sandboxing outside scope follows the
owner's existing boundary; no new security platform is added.

Cross-phase themes were shared-cost attribution, proof before rollout, cleanup
and supervisor survival, preserved evidence, usable fail-closed setup/migration,
and bounded checker overhead. Raw outside responses, model usage, voices,
decision audit, reality receipts and the 20-card test plan remain in the private
review archive. No completed review establishes full RL00 feasibility; the recorded RL00a
experiments establish only their stated observations.

## Owner choices

- UC1 (owner accepted A on 2026-11-04): reconcile the retained literal "cannot exceed its ancestor allowance"
  wording with documented kernel memory-limit semantics. Recommended direction:
  documented hard-limit behavior with measured transient slack and cleanup
  bounds, failing closed/no-go on unmet requirements. No automatic policy
  increase. Alternatively retain literal zero overshoot and record no-go if
  it cannot be proved. No weakening is applied before an explicit decision.
- D1 (owner accepted A): include effective-budget preview; alternative omit that small CLI addition.
- D2 (owner accepted A): retain mandatory per-case memory despite an unverified outside CEO
  suggestion to cut it from the first release. Cutting it changes the owner's
  stated outcome and requires affected reviews again.
- D3 (owner accepted A): retain existing exit-code families with stable typed IDs/JSON; alternative
  introduce a separate numeric exit code per resource subtype.
- D4 (owner accepted revised direction on 2026-11-04): investigate selective
  strict checking first and compare full standalone and worker instrumentation.
  Prove affected-input selection with full relevant-suite fallback for uncertainty
  and initial adoption; keep aggregate protection and canonical execution. Cheap
  signals alone cannot certify compliance. This is RL00 research, not a proven
  method; engineering must re-review completeness and total overhead.
- D5 (owner accepted A on 2026-11-06): prefer deterministic invocation-local worker shares; alternative dynamic
  allocation adds coordination/lifecycle complexity. Neither includes sharing
  capacity across independent projects.

The final plan decision approves this gated work plan only. Numerical values,
method feasibility and overhead criteria remain subject to RL00 and owner
review; product code, privileged setup, CI push, publication and merge were not
included in review approval. Later owner instructions authorized the recorded
RL00a executions; merge and product integration remain unauthorized.
