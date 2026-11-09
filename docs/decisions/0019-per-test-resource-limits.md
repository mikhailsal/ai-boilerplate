# 0019 Per-test resource limits are not adopted

Status: accepted (owner decision, 2026-11-09). The gate adds no memory budget
and no per-test limit. The research behind this decision is frozen in the Git
tag `archive/rl00-no-go`, which points to commit
[`d3e1fe3`](https://github.com/mikhailsal/ai-boilerplate/tree/d3e1fe3bd505c513c0942766229b69a9ea8fafd7).

## Question

Tests written by agents can exhaust a machine, or pile up expensive individual
cases while a suite is still small. The research, called RL00, asked whether
the gate can bound a whole test invocation and also reject a single expensive
case when it is added or changed. It used kernel-enforced limits (cgroup v2)
for every supported profile and had to leave coverage and scenario evidence
unchanged.

## Decision

Do not add per-test resource limits, a resource policy in `quality.toml` or
any memory budget to `quality`, its hooks or exported projects. The follow-up
integration phases of the research plan (RL01 to RL06) will not start. The
gate keeps the process supervision and cleanup it already has.

## Evidence

- Containing a whole invocation worked in the experiments: finite memory and
  task caps, placement before execution, an independent guardian and cleanup
  within milliseconds. All 26 host and prepared-subtree pairs of the first
  experiment passed in CI.
- Certifying each case did not meet the approved cost criterion. The protected
  run needed a fresh strict probe per case. For the browser corpus its p95
  wall time was 18.2 to 22.2 seconds against limits of 9.1 to 10.9 seconds,
  about five times the native run, in all four environments (x86_64 and
  aarch64, host and prepared). Even the fastest protected sample exceeded its
  limit. Each probe cost about two seconds, while instrumenting the canonical
  run cost almost nothing.
- Attribution was not proved for shared workers or for the browser `child`
  case, and no automatic cleanup was observed after the requesting process was
  killed. All 16 Dart jobs failed on setup problems, so no Dart result exists.
- The Node, PHP and Python correctness, compatibility, methods and timing cells
  (48 in all) never ran, so the cost result is measured for the browser only.
  The campaign stopped under a stop rule that the owner had approved.

The frozen record holds the plans, the protocols, receipts that bind every
result to its CI artifact by SHA-256, the timing samples, an outside review
and the experiment harness. Its starting point is the
[recommendation](https://github.com/mikhailsal/ai-boilerplate/blob/d3e1fe3bd505c513c0942766229b69a9ea8fafd7/docs/plan/test-resource-limits/rl00bc-recommendation.md).

## Consequences

- Nothing changes for users: there is no new prerequisite such as a delegated
  cgroup, and no new configuration.
- The problem stays open. Memory, task and time runaway are limited only by
  what the native runners and the host provide. A project that needs a hard
  cap today can apply one around the gate, for example in a container or a
  systemd scope; the gate neither sets nor checks it.
- The template's maintainer documentation states the
  [open problem](https://github.com/mikhailsal/ai-boilerplate/blob/main/docs/plan/bounded-test-execution.md)
  and where a solution could be sought.
- A new attempt needs a new protocol, a frozen commit and explicit owner
  approval. It may not reuse the rejected criterion after the fact: changing
  a criterion after seeing results needs a recorded amendment.
