# 0019 Per-test resource limits are not adopted

Status: accepted (owner decision, 2026-11-09). The gate adds no memory budget
and no per-test limit. The research behind this decision is frozen in the Git
tag `archive/rl00-no-go`, which points to commit
[`d3e1fe3`](https://github.com/mikhailsal/ai-boilerplate/tree/d3e1fe3bd505c513c0942766229b69a9ea8fafd7).

## Question

Tests written by agents can exhaust a machine, or pile up expensive individual
cases while a suite is still small. The research, called RL00, asked whether
the gate can bound a whole test invocation and also reject a single expensive
case when it is added or changed. The design required kernel-enforced limits
(cgroup v2) for every supported profile and had to preserve coverage and
scenario evidence.

## Decision

Do not add per-test resource limits, a resource policy in `quality.toml` or
any memory budget to `quality`, its hooks or exported projects. The follow-up
integration phases of the research plan (RL01 to RL06) will not start. The
gate keeps the process supervision and cleanup it already has. A whole-run cap
alone would leave the owner's per-case requirement unmet.

## Evidence

- Containing a whole invocation worked in the experiments: finite memory and
  task caps, placement before execution, an independent guardian and cleanup
  within milliseconds. All 26 host and prepared-subtree pairs of the first
  experiment passed on an x86_64 Ubuntu CI runner.
- Certifying each case did not meet the approved cost criterion. The protected
  run needed a fresh strict probe per case. The allowed p95 was twice the
  native p95 plus two seconds, including fallback. The protected browser run
  took 18.2 to 22.2 seconds at p95 against limits of 9.1 to 10.9 seconds,
  about five times the native run, in all four environments (x86_64 and
  aarch64, host and prepared). Even the fastest protected sample exceeded its
  limit. Each probe cost about two seconds, while instrumenting the canonical
  run cost almost nothing.
- Attribution was not proved for shared workers or for the browser `child`
  case. No automatic cleanup was observed within three seconds after the
  requesting process was killed. Fifteen Dart jobs lost their artifact uploads
  and one failed during bootstrap, leaving all 16 without a usable result.
- The Node, PHP and Python correctness, compatibility, methods and timing cells
  (48 in all) never ran, so the cost result is measured for the browser only.
  The campaign stopped under a stop rule that the owner had approved.

The frozen record holds the plans, protocols, timing samples, an outside review
and the experiment harness. The RL00b/c receipts record SHA-256 digests for 53
retained artifacts and cite job logs for 15 failed Dart uploads. Start with the
[recommendation](https://github.com/mikhailsal/ai-boilerplate/blob/d3e1fe3bd505c513c0942766229b69a9ea8fafd7/docs/plan/test-resource-limits/rl00bc-recommendation.md).

## Consequences

- Nothing changes for users: there is no new prerequisite such as a delegated
  cgroup, and no new configuration.
- The gate keeps its suite-level timeouts. For example, when a Python suite
  times out, the gate terminates its process group. Memory and task limits
  depend on the runner or host. A project can bound the whole invocation
  with a container or systemd scope. Per-case budgets remain an open problem.
- The template's maintainer documentation states the
  [open problem](https://github.com/mikhailsal/ai-boilerplate/blob/main/docs/plan/bounded-test-execution.md)
  and where a solution could be sought.
- A new attempt needs a new protocol, a frozen commit and explicit owner
  approval. Record any amendment to the cost criterion before the new run.
  The original measurements retain their verdict under the original criterion.
