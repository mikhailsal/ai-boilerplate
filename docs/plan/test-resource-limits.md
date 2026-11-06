# Design: bounded test execution

Initial office-hours design: 2026-10-31. Autoplan amendment: 2026-11-01.
Branch: `docs/test-resource-limits-plan`. Owner revisions: 2026-11-04/06.
Status: CEO, DX and affected engineering reviews completed with concerns and
explicit RL00 proof gates. Owner approved the plan and all choices on
2026-11-06. RL00a execution has begun under the later active owner goal;
[local evidence and remaining gates](test-resource-limits/rl00a-evidence.md)
are recorded separately. Product implementation has not started.

## Problem and intended outcome

Reject excessively resource-hungry tests, including agent-written tests,
against an explicit project budget. Protect exported projects first and use
the same mechanism in the template. Invocation/suite containment protects the
machine; individual case limits prevent expensive tests accumulating unnoticed
while the suite is small. Adding cheap cases cannot dilute a costly case.

Current native guards allow long suite runs, have no common memory budget,
and select Python workers automatically from CPU availability. Acceptance
suites can start nested gates and worker pools. Extend the existing engine,
process supervision, candidate isolation and native adapters.

The reviewed contract is split into linked pages:

- [Per-test budgets](test-resource-limits/per-test-budgets.md): accounting
  subjects, identity, detection scope and standalone/canonical execution.
- [Engineering contract](test-resource-limits/engineering-contract.md):
  hierarchy, supervision, worker capacity, evidence and policy proposal.
- [Verification](test-resource-limits/verification.md): staged feasibility,
  calibration, proof matrix and implementation dependencies.
- [Developer experience](test-resource-limits/developer-experience.md): setup,
  diagnostics, migration, proposed CLI and fresh-export trials.
- [Scope and review](test-resource-limits/ceo-scope.md): decisions,
  independent-review coverage and unresolved owner choices.

## Binding owner boundaries

- Mandatory memory protection fails closed locally and in CI. If protection
  cannot be established, start no test payload and explain the prerequisite.
- Bound invocation and suite memory, elapsed time and parallelism. Workers,
  owned children and nested quality commands retain ancestor limits/deadlines.
- Require individual time/memory protection including attributable setup,
  teardown and descendants; aggregate totals alone cannot certify a case.
- A breach fails. Never skip tests, lower coverage, hide failure with retries,
  automatically raise thresholds, or bypass hooks.
- Keep thresholds, classifications and justified scoped allowances solely in
  [quality.toml](../../quality.toml). Choose numbers from owner-reviewed
  measurements; no numerical defaults are selected by this plan.
- Configured budgets are independent of unrelated projects. A proven own
  breach is a resource violation; unavailable protection or an unknown external
  kill is an environment nonpass. Do not infer poor test quality from host
  free memory. No cross-project cap, queue or scheduler is included.
- Use integrated cgroup v2 management in a delegated hierarchy. An ordinary
  host may obtain delegation through systemd; prepared containers may supply
  a writable subtree. Neither mandatory Docker nor systemd-only deployment
  is required. Check actual capabilities before use.
- Retain Linux x86_64/aarch64 with glibc. Privileged preparation may establish
  delegation; payloads remain unprivileged. This protects against accidental
  exhaustion; hostile code with the same user's administrative access is
  outside the threat model.

## Architecture and compatibility

Use empty internal budget branches and bounded control/payload leaves.
Establish verified placement before execution and before costly preparation.
A child cannot enlarge configured ancestor ceilings or restart deadlines.
Bound supervisor overhead and reserve cleanup/report time inside the total
session envelope. Prove independent death cleanup on both provisioning paths;
late reconciliation on the next invocation is insufficient. Never kill an
unrelated invocation. The engineering page defines ownership and cause rules.

`process` owns cgroup primitives, supervision and primitive measurements;
`policy` validates values; `testing` carries context; the engine resolves
budgets; adapters map native execution. Preserve dependency direction:
`process` imports neither policy, adapters nor engine orchestration.

Keep canonical native coverage, scenarios, network isolation, generated
Dart/PHP imports and browser ownership intact. Preserve typed resource
outcomes through normalization, annotations, quarantine and reports.
An expected failure or quarantine cannot excuse an actual resource breach.
Missing, malformed or unsupported mandatory evidence cannot certify success.

Candidate revisions retain their own core/policy contract. Identify historical
pre-resource evidence explicitly; it cannot substitute for current protected
compliance. Migrate matching core/schema/policy together, verify prerequisites
before updating, and provide atomic rollback. Missing new mandatory policy
fails with migration instructions. Generate schemas through the existing CLI.
Fresh exports receive reviewed finite values; maintainer allowances stay
fenced out. Existing projects calibrate within explicit owner-reviewed finite
provisional limits, including case protection; no unbounded measure-only pass.

## Evidence and remaining uncertainty

Static inspection verified existing process cleanup, isolated candidates,
native runners, browser watchdog/subreaper and CLI/report contracts. A local
transient unit read back a memory limit, zero swap allowance and task limit;
this established settings only. The local older kernel lacks `memory.peak`.
No exhaustion, nested/death-cleanup, per-case method or live CI proof has run.
Exact peak telemetry is distinct from verified enforcement and attribution.

The review compared instrumentation, isolated execution and hybrid approaches.
On 2026-11-04 the owner selected selective strict checking as the first D4
research candidate, compared with full standalone execution and shared-worker
instrumentation. Prove selection of new, changed and affected cases; unknown
influence and first adoption require full relevant-suite coverage. Cheap signals
are diagnostic aids, not individual compliance proof. Retain canonical execution
and always-on aggregate protection. No method is proven. Shared mappings, warm
caches, fixtures and external services need explicit accounting or no-go.
Measure overhead and useful verdicts before selecting the method.

For UC1, the owner accepted documented kernel hard-limit semantics on
2026-11-04, subject to measured transient slack and cleanup bounds; the
prior wording said an over-budget payload "cannot exceed its ancestor allowance." Configured children cannot
enlarge ceilings, but Linux documents temporary `memory.max` overshoot.
Apply the accepted clarification during affected engineering re-review; do not
advertise an instantaneous zero-byte guarantee as proven. RL00 must
record containment semantics, measured slack and cleanup latency. If the
required guarantee cannot be proved, stop and return to the owner.

## Work sequence and acceptance gates

All implementation phases remain TODO. Each slice includes coherent code,
tests and indexed documentation and passes existing hooks without bypasses.
Retained spike artifacts must have proper existing quality-gate coverage.

| Phase | Deliverable | Evidence before proceeding |
| --- | --- | --- |
| RL00a | Preregister subjects/verdicts; establish topology and survival | Both provisioning paths, bounded exhaustion, nested/detached/death cleanup, supervisor reserve and kernel semantics |
| RL00b | Compare per-case methods and nested capacity | Highest-risk Dart/browser first, then PHP/Python; shared costs, variants, children, canonical parity and attributable case protection |
| RL00c | Calibrate usefulness, overhead and adoption | Labeled ordinary/excessive/justified cases; native/protected comparisons, residual charges/churn, fresh-export/update and full setup timing |
| RL01 | Freeze policy, migration and setup contracts | Reviewed units, defaults, classes, overrides, inheritance, detection scope, schema generation and fail-closed prerequisites |
| RL02 | Shared execution and evidence lifecycle | Aggregate/case limits, nested deadlines/capacity, abrupt-parent cleanup and preserved structured evidence |
| RL03 | Every native profile and browser ownership | Python, Node/browser, Dart and PHP identity, workers, isolation, coverage and scenarios |
| RL04 | Hooks, nested gates, export and updates | Costly case rejected in a small suite; cheap additions/source/fixture changes cannot bypass; history and export fences preserved |
| RL05 | Reports, calibrated values and documentation audit | Safe attributed diagnostics, reviewed norms/overhead, setup, remediation and migration examples |
| RL06 | Full validation and handoff | All proofs, applicable suites, authorized live GitHub gate, SHAs and residual limitations |

Each RL00 stage stops on failed required proof. RL01-RL06 product integration
requires a reviewed RL00 go/no-go record. No profile silently falls back to
suite-only certification. Proof obligations and implementation dependencies
are detailed in the verification page. Numeric limits, acceptable overhead
and supported capability rows require evidence and owner review.

## Success and distribution

An over-budget payload fails promptly, retains ancestor constraints, produces
an attributed result and leaves no owned descendants after the specified
cleanup deadline. Unsupported hosts start no payload. Independent invocations
cannot confuse ownership. A costly individual case fails below suite totals;
setup and owned descendants remain accounted for. Missing measurements remain
explicit and the checker meets its approved bounded overhead criterion.
The runtime guarantee follows the owner-accepted UC1 clarification above.

Distribute through existing template export/update flows. CI is a thin
provider-specific provisioning wrapper around the same CLI. No hosted service,
new registry, historical resource dashboard or mandatory image is included.
Document prerequisites and migration cost before release.

## Next handoff

The owner approved this gated plan on 2026-11-06 and later activated the RL00a
execution goal. The [bounded protocol](test-resource-limits/rl00a-protocol.md)
and [local evidence](test-resource-limits/rl00a-evidence.md) are available.
Review the prepared CI experiment and obtain its separately required approval
before publication and the real GitHub run. Product integration and merge
remain outside this stage. Historical office-hours PASS and plan approval do
not establish live feasibility.
