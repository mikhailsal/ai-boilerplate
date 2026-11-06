# Developer experience for bounded test execution

Status: owner-approved plan, 2026-11-06. Live feasibility proofs remain pending. This document does not authorize implementation, privileged setup,
publication, or a CI run. It records the accepted developer experience for the
[resource limits plan](../test-resource-limits.md); proposed interfaces and
unmeasured outcomes are identified below.

## First protected result

Provide copy-paste paths for a prepared host and for a host that needs an
administrator. Both use the existing bootstrap, doctor, test, and check
surfaces. `quality` must never escalate its own privileges. The administrator
path states exactly what must be supplied or changed, why, its blast radius and
undo, and a read-only verification command. An unsupported environment that
would schedule tests fails closed with an explicit human handoff. A check that
schedules no tests retains its existing no-delegation requirement.

Doctor must distinguish controller availability, permissions, a writable
delegated subtree, kill support, and user-manager/runtime capabilities. These
read-only probes do not claim an OOM enforcement experiment succeeded; an
explicit bounded live or self-test proof is separate. Recheck relevant changes
in the environment. Inventory and prepare supported contributor and CI
environments before mandatory rollout.

The provisional time-to-hello-world target is **under five minutes**, but it
has not been measured. Start at a fresh supported checkout or export and stop
at the first understood protected result for the user's own test. Include
reading, bootstrap, download/cache state, delegation preparation, active work,
and administrator waiting. Record total, active, and waiting time separately,
along with runtime versions and capabilities. Trial both prepared and initially
unprovisioned paths; do not promise one-command installation or no CI setup.

## Upgrade and policy

Before updating a project, provide a reviewed prerequisite probe or isolated
new-core diagnostic that works while the old core is still installed. The old
doctor alone cannot establish readiness for the new contract. Migrate and
calibrate policy with the matching core and provide a matched rollback path.
The new core must reject missing required resource policy before tests, with
migration instructions; it must not invent permissive values. Historical
candidates run with their own core and policy, and their pre-resource evidence
is distinct from current protected compliance.

[quality.toml](../../../quality.toml) remains the sole source of thresholds and
scoped allowances. Reducing the cost of a test, fixture, parameter, or owned
child is the first remedy. An allowance needs exact scope, justification, and
policy-owner review. Numerical values and final policy syntax require evidence
and owner review; no automatic threshold increase is authorized.

## Diagnostics and recovery

Register stable resource diagnostic IDs with explain and documentation anchors
for invalid policy, missing or partial delegation, proven case, suite, and
invocation violations, invalid ancestry, unknown kills, unsupported attribution,
invalid evidence, cleanup failure, and unexpected supervisor, parser, or
process faults. Existing exit families with machine-readable subtypes are the
owner-accepted D3 decision; the final plan was approved on 2026-11-06. An ambiguous kill or
aggregate-only evidence cannot establish a successful per-case result.

Each resource error identifies the attempted operation; safe component, suite,
case, and variant identity; configured and effective boundaries, units, source,
and restricting ancestor; observed value or cap proof and measurement quality;
causal basis; and safe runtime, version, and configuration context. Show only
environment variable names. Put the exact safe action or human prerequisite on
the first or last line. Expected failures report recovery and cleanup status;
unexpected failures also provide an invocation ID and a bounded, private,
redacted trace or artifact. Validation before work needs no invented side
effects or trace.

Report side effects as none, partial, complete, or unknown. Reconcile owned
state before retrying after partial or unknown cleanup; allow at most one
explicit post-repair retry before escalation. Do not recommend unchanged
automatic retries, hook bypasses, broad process killing, forged ancestry, or
ready-made diagnostic override snippets. If a worker dies, queued collateral
cases are unexecuted, not passed or silently retried. Identify an offending
case only when causal evidence supports it; otherwise report unknown case
attribution with the suite or environment failure.

Resource failures use nonzero existing CLI exit families and human diagnostics
on stderr. JSON is one complete stdout document containing equivalent safe
fields, without progress or traces. Preserve unrelated output contracts. Redact
parameter values, command arguments, nested causes, and unexpected traces; use
opaque variant identity where necessary. Verify secret-shaped parameters and
credential URLs, since terminal escaping alone is not redaction.

## Preview and reproduction

The proposed candidate-aware effective-budget preview and execution resolve the
same staged-by-default candidate or explicit revision, norms, source scopes,
and ancestor restrictions. Preview launches no tests or native collection or
preparation and requires no writable delegation. It reports unavailable
capabilities. The owner approved preview inclusion; exact CLI spellings
remain an RL01 decision.

The engineering proposal calls this future surface `policy budgets`, with
proposed `--rev`, `--component`, `--suite`, and `--json` options. These are not
claims that the command or flags exist today. Existing test/check/gate selectors
remain; a new per-case selector is only a possibility after identity and setup
semantics are proven. A reproduction hint uses the narrowest supported,
argument-safe, enforced quality command that preserves charged setup. A
protected suite rerun remains available; an unbounded native rerun cannot
certify compliance.

Optional future progress is explicit opt-in, bounded, and sent to stderr;
optional rankings use current-run data. Neither changes the mandatory per-case
contract or contaminates JSON output.

## Documentation and proof

Ship and index setup and administrator guidance, quickstart, accounting
explanation, policy and CLI references, support matrix, migration and rollback,
and rule-ID troubleshooting with their implementation slices. Update AGENTS,
extension and profile guidance. Include clearly labelled illustrative
text and JSON examples for missing telemetry, an own-budget breach, an
environment failure, and a justified expensive-case allowance; do not present
illustrations as captured runs.

RL05 audits documentation. Real fresh-export, update, and hook acceptance must
exercise copy-paste instructions, matched migration and rollback, preview
parity, and golden text/JSON diagnostics, redaction, and noninteractive
recovery. Record whether users can identify the effective budget and reason.
No hosted analytics, recurring survey, or additional platform is authorized.
The reviewed DX specification is not evidence of a working implementation,
protected run, or measured first-use time.

Selective checking reports native execution and strict individual verification
separately, together with safe selection/fallback reasons. Canonical suite
success never implies strict verification of every case. Explain insufficient
checker capacity without inventing case violations; preserve any actual ancestor
limit failure. Available runtime-pressure context does not excuse a known own
wall-time deadline breach. Capability diagnostics distinguish event/mount
semantics and visible versus unavailable ancestor evidence.
