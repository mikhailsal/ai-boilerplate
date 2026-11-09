# Test resource limits: engineering contract

Status: prior reviewed proposal; the owner selected revised D4 research on
2026-11-04. Affected engineering re-review completed on 2026-11-06 with
explicit RL00 proof gates. Owner approved the plan on 2026-11-06.
[RL00a](rl00a-remote-evidence.md) is technically complete within its recorded
limits; RL00b and RL00c ran in part on 2026-11-09 and ended in a
[no-go recommendation](rl00bc-recommendation.md). The owner selected D5=A on
2026-11-06. The reviewed plan itself did not authorize execution; later owner
instructions authorized the recorded experiments. Merge and product integration
are not authorized. Historical office-hours approval applied only to the initial
design and is superseded for this amendment.

## Boundaries and topology

Exported projects and the template use the same integrated delegated cgroup
v2 mechanism on supported Linux x86_64 and aarch64 with glibc. Mandatory
memory protection fails closed before a test payload starts. Aggregate memory,
elapsed time and parallelism are bounded; nested commands and workers cannot
enlarge ancestor ceilings or restart deadlines. No automatic skips, coverage
cuts, hidden retries, budget increases, shared project cap or host scheduler
are authorized. The mechanism addresses accidental exhaustion, not hostile
same-UID code. External services outside the owned subtree are not automatically
accounted for.

The hierarchy is delegated root, invocation budget, suite budget, and worker
and nested-command boundaries, with additional case enforcement as proved by
RL00. Use empty domain branches, bounded control and payload leaves, top-down
controller enablement, and a placement barrier before exec. A parent worker
remains in a leaf when a nested branch is created. Ordinary-host delegation and
a prepared writable subtree are provisioning paths to the same mechanism;
detect actual capabilities and do not fall back to unbounded execution.

Configured ceilings and actual kernel containment are distinct. RL00 must
document transient memory overshoot and cleanup latency and obtain an owner
decision on any weaker runtime guarantee. If literal zero overshoot remains
mandatory and cannot be proved, the result is no-go.

## Lifecycle, ownership and capacity

After bounded minimal candidate and policy preflight, establish the invocation
envelope before costly test-associated materialization, preparation, builds or
collection. A check selecting no suites and a read-only preview need no test
session. Bootstrap outside a session retains its existing guards; nested
bootstrap and candidate-core work remain within their ancestor envelope.

The total monotonic session deadline covers preparation, native execution,
reporting and cleanup. Derive a payload-stop deadline with explicit cleanup
and reporting reserve; document CLOCK_MONOTONIC suspend behavior. Bound control
memory and tasks within the total and prove supervisor survival under case,
suite and invocation pressure. Both provisioning paths require a proven
independent death/fallback enforcer; an end-of-run timeout or late stale-group
cleanup alone is insufficient. Incomplete cleanup cannot pass.

Validate ownership using current verified membership, allowed delegated root,
unique invocation identity, safe descriptor/path lifetime and namespace view.
An environment value or stale/reused path alone grants no authority. Serialize
launch admission with CLOSING and verify both launch/cleanup orders. Observed
membership or limit drift is a non-exceptable integrity failure. Cleanup must
remove owned detached descendants without killing another invocation.

Owner-selected D5 investigates deterministic invocation-local capacity shares before native
launch. Live parents consume their shares and nested pools receive only
remaining preassigned capacity. Set native worker ceilings explicitly, bound
helper threads separately, and fail impossible allocations promptly without
deadlock or cross-project borrowing. Display a conservative effective worker
count derived from proved policy, quota, task and memory allocations; reject
invalid reserves, units and impossible positive-work allocations without
assuming every maximum is actually reserved. Prove forward progress, aggregate
counts and recovery before selecting this mechanism for integration. CPU quota,
framework workers and tasks/threads are separate limits.

## Case subject and attribution

D4 now investigates selective strict checks first, with proven affected-input
selection and full relevant-suite fallback when uncertain or first adopting.
Include source, fixture, parameter, data, dependency, runtime and configuration
changes; test-text-only selection is insufficient. Always retain aggregate
protection and canonical native semantics, coverage and scenarios. Cheap signals
are diagnostic aids, not proof of individual compliance. Compare against full
standalone workloads (fresh runtime, required imports, collection, setup, call,
teardown and children) and worker instrumentation. Measure total cost including
broad fallback; the owner selected research direction, not a proven method. Define
kernel-charged memory and any desired physical/resident cost, including shared
mappings, warm caches and services. Reused worker migration, preloaded fork
state, RSS deltas, worker lifetime peaks or suite averages cannot alone certify
the full subject. If required shared costs cannot be attributed, report
unavailable and no-go. Verified cap compliance can be established without an
exact peak where proved; distinguish exact, sampled, unavailable and worker-only
measurements, never treating missing values as zero.

Retain component, suite, native case ID, parameters and browser/runtime variant
through parsing, normalization, annotations, retries, invalidation, quarantine,
reports and scenario judgment. Missing, duplicate, stale, truncated or unknown
mandatory evidence fails. Expected failure or quarantine cannot erase a
resource violation. A worker death leaves collateral queued cases unexecuted;
identify an offender only with causal proof. Preserve canonical coverage,
generated Dart/PHP imports, network isolation and browser ownership; a separate
probe cannot replace native coverage or scenario proof.

Keep a fresh bounded invocation-local selection record tied to candidate and
comparison identity, resolved policy, profile/runtime inputs and discovered
opaque case/variant identities. Store selected scope and fallback basis;
separate native outcome from strict verification status in models and reports.
Selected cases without strict evidence, unexpected variants or mismatched scope
inputs expand selection within remaining budgets or fail. Canonical-only cases
never inherit individual compliance from suite success. Scope widening cannot
rescue an actual breach, reset a deadline or introduce a resource-verdict cache.
Trustworthy comparison/influence proof is mandatory for narrow selection;
otherwise retain full relevant-suite checks.

Define detection scope for test, parameter, source and shared-fixture changes
before integration. Use proved selection or all cases of selected suites; an
unproved diff heuristic or unchanged test text cannot bypass the check. Shared
setup must not be hidden or blamed on its first consumer.

Use fresh boundary-local and ancestor event baselines and a proved cause table
for each resource. A caught own allocation or task denial fails even with a
successful native exit. Successful reclaim or CPU throttling alone is not a
breach. Attribute ancestor exhaustion to that ancestor, not automatically to
the killed sibling; an external or unknown kill is an environment nonpass.
An intentionally failing inner probe remains an inner failure that a valid
outer test may assert if its own limits and integrity hold. Preserve all proven
causes and cleanup findings through existing exit precedence. CPU accounting is
separate from the fixed wall deadline.

## Operation and layer map

Canonical execution and generated imports belong to suite/shared setup;
standalone workloads belong to cases. Coverage formatting, parsing and scenario
judgment remain under the enclosing suite or invocation; output and cleanup use
reserved control capacity. Bound report sizes, case counts and post-native
execution using existing bounded I/O contracts. Nested launcher work remains
under its ancestor.

`process` owns cgroup operations, supervision, cleanup and primitive
measurements; it must not import policy, adapters or engine orchestration.
`policy` validates limits, `testing` carries execution context, the engine
resolves effective budgets, and adapters map worker ceilings to native runners.
Structured resource outcomes must survive adapter errors and engine judgment;
generic tool failure wrapping must not erase identity or recategorize a proven
violation as an environment failure.

## Policy and migration proposal

After RL00, freeze a strict new schema version with the matched core. The
candidate `test_resources` namespace has invocation limits, suite defaults by
kind, case defaults by profile/kind, and exact justified owner-scoped overrides
in `quality.toml`. Specify positive integer `memory_bytes`, explicit
`swap_bytes` semantics, `elapsed_ms`, `framework_workers` and `tasks`;
`control_memory_bytes`, `control_tasks` and `cleanup_ms` subdivide totals.
Specify quota/period units if CPU quota is configured. Reject unknown fields,
coercion, unlimited mandatory memory, invalid reserves and scopes above
ancestors. Overrides identify exact component, suite, case and variant scope,
justification and policy owner. Numerical defaults require owner-reviewed
calibration; no automatic historical ratchet is authorized.

The proposed read-only budget preview resolves the same staged-by-default or
explicit revision policy and ancestor restrictions as execution without native
collection, preparation or writable delegation. Its precise CLI spelling is an
RL01 decision, not an existing command. Optional bounded progress on stderr
and current-run rankings are proposed; JSON stdout remains clean. A case
selector is optional only after identity and charged-setup semantics are proved;
the protected suite rerun remains available.

New exports receive explicit reviewed policy; maintainer allowances are fenced
out. New core rejects missing policy before tests with migration instructions;
historical candidates use their own core and are labeled as pre-contract, not
current protected proof. Provide matched migration, calibration and atomic
core/policy rollback, and a prerequisite probe usable before updating the core.
Generate schemas through the existing schema command. Resource-enforcement
rules are non-exceptable, with stable diagnostics and remediation. The
verification gates are in [verification.md](verification.md).

Under owner-accepted D3, resource diagnostics use existing nonzero exit families with stable
machine-readable subtypes, and explain the attempted operation, safe identity,
effective boundary, units, source and restricting ancestor, observed value or
cap proof, measurement quality, cause, safe context and action. Report cleanup
and side effects as none, partial, complete or unknown. Reconcile partial or
unknown owned state before retry; after repair permit at most one explicit
retry before escalation. Remediation first reduces workload cost; allowances
need justification and policy-owner review. Never suggest broad process killing,
forged ancestry, automatic retries, threshold increases or hook bypass.
Redact parameter values, argv, nested causes and traces; use opaque variants
where necessary. Unexpected faults add a bounded private redacted trace and
invocation ID. Reproduction hints are argument-safe and use the narrowest
proved protected selector, never shell-interpolated case names.

## Additional proof constraints from re-review

Record relevant mount/event semantics and ancestor-counter visibility in the
capability matrix; unknown ancestor/global kills remain environment nonpasses.
Use opaque generated group names and verified operations under the delegated
root, refusing symlink/path escape. Prove placement without threaded pre-exec
hazards, name an independent enforcer for each provisioning path, and verify
time-namespace handling. Specific shim/watchdog layouts or newer-kernel features
are experimental candidates, not assumptions of success.

Account for checker and test work separately inside the same finite total.
Insufficient checker capacity is a distinct nonpass explanation, not evidence
that an otherwise compliant case exceeded its norm. An actual ancestor breach
still belongs to that boundary. Use defensible preflight information, not an
average startup estimate as proof that work fits. Freeze subdivisions and subtype
mapping in RL01; no extra unbounded checker pool or automatic allowance is added.

Wall limits remain elapsed-time contracts under declared runtime/concurrency
conditions. Report available CPU/throttling/pressure context without excusing a
known own timeout, adapting thresholds or claiming contention-independent
intrinsic cost. Preserve every cause and cleanup finding. Unit coverage floors
retain their existing ownership; unrelated e2e coverage cannot rescue them.
Real-kernel behavior requires authorized delegated proofs alongside meaningful
boundary tests; mocks alone do not establish containment.

Keep process supervision/cleanup and engine selection under single owners.
Expose a supported facade, route captured/attached/nested execution through the
same session contract, and add a failing boundary/type-check case for forbidden
internal imports. Compare ownership shapes before freezing exact signatures;
no new service is selected. Preview and execution share one resolver, and
identity sets are reconciled rather than maintained as separate copied lists.
