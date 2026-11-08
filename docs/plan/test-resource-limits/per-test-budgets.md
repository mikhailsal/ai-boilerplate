# Per-test resource budgets

Status: REQUIRED outcome. Owner approved selective-first D4 research on
2026-11-04. Affected engineering re-review and final owner plan approval
completed on 2026-11-06. RL00a is technically complete within its
[recorded limits](rl00a-remote-evidence.md); RL00b and RL00c are unperformed.
Source: [amended design](../test-resource-limits.md) and the owner's question
about expensive individual tests passing while the suite is still small.
The owner requested skill-based plan refinement after this gap was identified.
The required outcome is adopted; no collection method or implementation is
approved by this page. The proposed method below must pass RL00.

## Why aggregate limits are insufficient

A small suite can remain under its total budget while every test is too costly.
Later additions then expose accumulated debt to an unrelated contributor.
Adding cheap cases must not dilute or hide an expensive case. An average cost
per test or a suite peak divided by case count cannot establish this property.

The initial design committed to invocation and suite budgets only. The normalized
`CaseResult` in `tools/quality/src/quality/testing/model.py` contains identity,
outcome, and scenario evidence, not resource measurements. The JUnit parser
does not preserve a testcase duration. Native timing data alone is not an
implemented per-test resource gate.

## Required outcome for CASE-01

Make a test case an individually identified subject of resource evidence and
configured time/memory budgets. A proven per-case breach must fail even when its suite and
invocation remain under their aggregate ceilings. Existing aggregate protection
remains mandatory and separate. Check cases when introduced or modified rather
than waiting for a later aggregate limit failure; do not treat historical debt
or a growing case count as justification for automatically raising thresholds.

Budget classes must distinguish unit, integration, contract, e2e and acceptance
work. Keep values, classifications, and any justified overrides in policy;
choose numbers from measurements. No numerical values are proposed here.
The same norms apply when cases enter the project, so an adding/modifying PR
exposes excessive individual cost rather than leaving it to a later contributor.
Define detection scope for test edits, parameter changes, and source/fixture
changes affecting existing cases; unchanged test text is not proof of unchanged
cost. Do not select tests from a source diff using an unproved heuristic.
A historical regression ratchet is not automatically included. Absolute
per-case norms are distinct from comparisons with previous executions.

## Measurement contract to resolve

- Preserve stable identity: component, suite, native case identity and relevant
  parameters/execution variants. Browser-project/viewport runs may not be
  silently collapsed before resource evidence is judged. Respect the existing
  prohibition on retries hiding a failure.
- Define whether setup, call and teardown are separately reported and how their
  sum contributes to the case budget. Hidden expensive setup must not disappear.
- Account for shared fixture/runtime setup explicitly. Do not charge it
  inconsistently to whichever case happens to run first, or omit it entirely.
- Distinguish wall duration and CPU consumption, and state their dependence on
  runtime conditions. Unrelated projects must not change the configured budget.
- Attribute memory and owned descendant costs to the measured execution unit.
  A shared worker's lifetime peak is not automatically a case's memory peak.
- Under parallel execution, declare which measurements are exact, sampled,
  unavailable or only attributable to the worker/suite. Never label a suite
  measurement as an individual measurement or turn missing values into zero.
- Preserve the distinction between an attributable budget violation and an
  environment failure. Neither an unsupported measurement contract nor an
  uncertain external kill may silently certify that a case met its budget.
- Keep exact peak telemetry separate from proof of enforcement. A verified
  isolated hard cap may establish compliance even where exact peak reporting
  is unavailable. Missing attribution or absent mandatory protection cannot.

Engineering review must compare framework instrumentation, isolated execution,
and a hybrid against the same accounting contract for every supported profile.
An isolated execution may alter fixture reuse and startup cost; instrumenting
a persistent worker may not attribute native/child memory accurately. Do not
select one process per test, RSS deltas, or worker peaks by assumption.
Cgroup limits around a whole suite do not establish per-case attribution.

## Owner-selected research direction (D4)

On 2026-11-04 the owner selected selective strict checking as the first RL00
candidate, after challenging fresh-runtime startup overhead. This approves a
research direction, not implementation or an executed feasibility experiment.
Compare it with complete standalone execution and shared-worker instrumentation
against the same expected verdicts and overhead criteria.

Keep hard invocation/suite protection active for every ordinary run. Strictly
check new, modified and affected cases, including changes to source, fixtures,
parameters, test data, dependencies, runtime and configuration. Test-text-only
selection is insufficient. Prove the affected-input scope; uncertain selection
expands to the full relevant suite. Initial adoption requires complete relevant
suite coverage. The existing component/dependent selector is conservative and
may select almost everything; no case-level selector is implemented yet.

Cheap duration, worker-memory or resource-event signals can trigger detailed
diagnosis. Absence of a signal cannot certify individual memory compliance.
Do not replace mandatory checks with sampling or periodic-only audits, and do
not introduce a resource-verdict cache through this change. Selection and
accounting must both be proved; a failed proof means no-go or owner review.

Bind selection to a bounded fresh invocation-local scope record: candidate and
comparison inputs, resolved policy, profile/runtime inputs, discovered opaque
case/variant identities, selected set and selection/fallback basis. Keep native
execution outcome separate from strict individual verification in all reports.
Every selected case needs valid strict evidence. Missing selected cases,
unexpected variants or mismatched inputs widen selection within remaining
budgets or fail; they cannot silently pass. Canonical-only cases gain no
individual-compliance evidence from aggregate success. A wider check never
erases an actual failure or resets an ancestor deadline. This record is not a
resource-verdict cache. Trustworthy comparison and influence analysis remain
RL00 proof obligations; otherwise use full relevant-suite checking.

For the standalone comparison, include a fresh runtime, required imports and
collection, setup, call, teardown and owned descendants. Retain canonical native
suite execution for fixture semantics, coverage and scenarios. Probe success
cannot replace canonical evidence. A fresh process per case on every invocation
is not selected in advance. Measure selection cost, fallback frequency and total
protected runtime, including broad source-change and first-adoption cases.

Define kernel-charged memory separately from physical/resident memory. Charges
can stay in the allocating group after migration; shared mappings and warm
caches can be charged elsewhere. Moving a reused worker, measuring RSS deltas
or forking preloaded state alone cannot certify the complete subject. Explicitly
account for shared fixtures/runtime, browser servers and external services;
if required cost cannot be attributed, report unavailable/no-go. Do not transfer
shared cost to whichever case happens to run first.

Own allocation or task denial fails even if the test catches it and exits zero.
Successful reclaim or CPU throttling alone is not a breach. Attribute an ancestor
hit to that boundary rather than automatically blaming its OOM victim. An inner
negative probe remains a failed inner invocation; an outer test may assert it
only while its own limits and integrity remain satisfied.

## RL00 preregistration

Use kernel-charged memory of the declared case subject as the cap quantity;
define included accounting categories and explicit separate swap semantics
before comparing methods. Runtime heap counters, RSS deltas and allocator
baselines cannot certify whole-subject cost. Record available memory categories
without double counting; unsupported exact peaks remain unavailable. Include
retained allocator memory, shared charges, successful file-cache reclaim and
native/child allocations in expected verdict examples.

For each profile list execution model, certifying method candidates, expected
unsupported cells and semantic changes from process/file isolation. Shared VM,
thread or browser modes need proof beyond a runtime heap counter. No certifying
method means unsupported attribution/nonpass, never a neighbouring culprit.

Reuse existing candidate/comparison semantics for staged, revision and explicit
CI contexts; preserve full canonical CI suites. Bind every scope to those
identities. Unknown dynamic dispatch, data dependencies and volatile inputs
(randomness, clock or uncontrolled services) widen selection. No persisted impact
map is approved. Any new persistent trust mechanism needs owner review.
Cheap signals may require diagnosis but cannot certify compliance. A known
breach remains failure even if a later strict check adds attribution.

## Implementation-plan changes

Extend RL00 to demonstrate valid case attribution on every supported runner,
including shared setup, parameterized cases, child processes and parallelism.
If a profile cannot meet the contract, stop that rollout with evidence and
return to the owner; do not downgrade it silently to suite-only enforcement.

RL01 must define case-level defaults, suite-kind classes and explicitly scoped
policy overrides without inventing numerical defaults. Record any justification
and owner requirements for costly cases; increasing norms remains a policy
decision, never a formatter or automated repair.

RL02/RL03 must preserve case evidence throughout normalization, annotations,
coverage/scenario processing, and native adapters. Current JUnit parsing drops
case timing; Dart event IDs are not retained as measurements; Playwright
collapses project outcomes. Those existing representations need explicit
compatibility and identity tests, not just fields added to `CaseResult`.

RL04 must prove early rejection through a real adding/modifying commit and
hooks/export flow. RL05 must identify the case, phase/measurement boundary,
configured norm, observed value or cap-based proof, and environment conditions
in consistent terminal/JSON results. RL06 verifies the complete contract;
report rankings alone cannot satisfy it.

## Cost of the resource check itself

Measure the additional wall/CPU time, peak memory and process count against
the native runner on representative small and larger suites per profile.
Record instrumentation/coverage mode, fixture reuse, startup and collection
cost, worker count, runtime versions and environment. Agree acceptable overhead
and measurement scope before release. The resource checker and its extra
processes remain within invocation/suite budgets; they receive no unlimited
side channel. Do not claim a cheap or reproducible gate without this proof.

## Required proof

1. A single expensive case fails its own budget while the entire small suite
   remains below its aggregate budgets.
2. Adding cheap cases cannot make that case pass.
3. Slow or allocation-heavy setup is visible under the declared accounting rule.
4. Reordering cases and changing worker assignment cannot silently transfer an
   expensive case's cost to a cheap case; shared costs remain explicit.
5. An owned child process cannot hide a case's consumption outside its accounting.
6. Unsupported or ambiguous per-case measurement is explicit, with no fabricated
   successful measurement; suite limits still protect the run.
7. Parameterized/browser variants retain the correct identity and resource
   evidence through normalization and annotations; retries cannot turn a
   resource failure into a pass.
8. Test/source/fixture changes exercising the chosen detection scope cannot
   bypass the case gate merely because the test function's text did not change.
9. The measured resource-check overhead meets its approved release criterion;
   the checker cannot escape the very aggregate budgets it enforces.

## Disposition

The required goal is early detection of resource-hungry individual tests.
The architecture, exact measurement/selection protocol, numbers and release
overhead threshold remain open for RL00 and owner review; the provisional method above is not proven. The plan-refinement request did not authorize product implementation, machine
reconfiguration, CI push or budget relaxation; later owner instructions
authorized the recorded RL00a executions. Product integration remains unauthorized. The earlier initial-design verdict
does not cover this amendment; final approval covers the reviewed plan only.
