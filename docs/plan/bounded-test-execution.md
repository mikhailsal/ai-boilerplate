# Bounded test execution: the open problem

Status: written on 2026-11-09, after the owner accepted the RL00 no-go
recommendation ([decision 0019](../decisions/0019-per-test-resource-limits.md)).
This page states the problem and what the research established. The
[causes page](bounded-test-execution-causes.md) explains why no solution has
been found, and the [directions page](bounded-test-execution-options.md) lists
where one could be sought. Nothing here is a plan or an approval: a new attempt
needs its own protocol and owner approval.

## Summary

Bounding a whole test invocation worked in the experiments, with one open gap:
cleanup after the process that launched the tests is killed. The unsolved part
is the owner's second requirement, an individual time and memory verdict for
every test case, given when the case is added or changed, that cheap cases
cannot dilute. The only method the research accepted as certifying a case, a
fresh strict probe per case, cost about five times the native run on the one
profile that was measured. Cheaper methods lose attribution, and a sound choice
of which cases to probe is unproved. The negative result is one design on one
profile plus a long list of unknowns. It does not prove that the problem has no
solution.

## The problem

Tests written by agents can harm a machine or a project in two ways.

- Machine exhaustion: a test, or a tool it starts, allocates too much memory,
  creates too many tasks or never ends. The host slows down, the kernel kills
  an unrelated process, or the hook or CI job hangs.
- Hidden accumulation: every case is costly, yet the suite stays under each
  suite-wide limit because it is small. The debt surfaces later, when an
  unrelated contributor adds tests and the suite finally crosses a limit.

The owner asked for both to be handled. The first needs a bounded envelope
around the whole invocation. The second needs a verdict for each case, given
when the case is added or changed and independent of how many other cases
exist, so that adding cheap cases cannot dilute a costly one. The native guards
that exist today allow long suite runs, have no common memory budget and choose
the number of Python workers from the available CPUs.

## What the owner required

The binding boundaries come from the archived design and are paraphrased here.

- Fail closed. If protection cannot be established, no test payload starts,
  locally or in CI, and the gate names the missing prerequisite.
- Use kernel limits (cgroup v2 in a delegated hierarchy) with a cleanup path
  that survives the death of the launching process. The target is accidental
  exhaustion on Linux x86_64 and aarch64 with glibc; hostile code is out of
  scope.
- Treat each case as a subject with its own time and memory budget, including
  its setup, teardown and child processes. Aggregate totals cannot certify a
  case.
- Never skip tests, lower coverage, hide a failure with retries, raise a
  threshold automatically or bypass hooks. Thresholds live in `quality.toml`.
- Keep canonical native execution, coverage, scenario evidence and browser
  ownership intact for all five execution models: Python, Node unit tests,
  browser tests, Dart and PHP.
- Do not downgrade a profile silently to suite-only enforcement. A profile
  that cannot meet the contract stops with evidence and returns to the owner.
- Selective checking was the first research candidate. Strictly check new,
  modified and affected cases, and fall back to the whole relevant suite for
  unknown influence and for first adoption. Cheap signals may trigger a
  diagnosis but never certify compliance. No persisted impact map is approved.
- Keep the checker's own overhead inside an approved criterion. Criterion A,
  accepted on 2026-11-09 before any measurement, allows a protected p95 wall
  time of at most twice the native p95 plus two seconds, fallback included.

## What the research established

RL00 was the research phase of the design. RL00a built and tested the
containment foundation, RL00b compared per-case methods and RL00c measured
overhead and adoption. The campaign ran on frozen commit `9acec68` and all heavy
work ran in CI.

| Finding | Evidence |
| --- | --- |
| Whole-invocation containment works | All 26 host and prepared pairs passed on an x86_64 Ubuntu 24.04 runner: finite caps, placement before execution, own versus ancestor attribution, and a guardian that emptied a leaf in 0.019 to 5.15 ms. The fallback after guardian death took about 1.27 s. |
| Kernel limits are not exact | A dirty-page writer's kernel peak exceeded its 32 MiB ceiling by 4 KiB, and residual charges after a kill were sometimes nonzero. Page-cache reclaim needed an owner-approved fixture amendment after the first two CI runs failed. |
| The lifecycle held in fixed fixtures | Admission, nested budgets, limit and membership drift and both guardian races matched expectations in four Python cells (x86_64 and aarch64, host and prepared). |
| Instrumenting the canonical run is cheap | The instrumented run matched the native median within 0.03 s in every browser cell. |
| Fresh per-case probes are expensive | In the browser corpus of eight cases each probe took 1.80 to 2.21 s. Protected p95 was 18.2 to 22.2 s against limits of 9.1 to 10.9 s, about five times the native p95 of 3.5 to 4.4 s, in all four environments. Even the fastest protected sample exceeded its limit. |
| Narrow selection is unproven | Selection pressure and 19 candidate steps passed on a finite Python fixture. The evidence claims no selection soundness and never measured the cost of narrow selection. |
| Attribution is the weak point | Shared-worker attribution was recorded as unsupported. The browser `child` case had a bound identity but no valid allocation-phase attribution. |
| Abrupt requester death is not covered | After SIGKILL of the requesting process, no automatic cleanup was observed within three seconds in four of four cells. The cause is unattributed. |
| Onboarding is mostly unmeasured | Python overlay chains took 94 to 138 s to the first protected own test, without administrator wait. One chain failed its update check for an unattributed reason. |

The negative result has a narrow scope. Only the browser profile completed a
timing cell. All 16 Dart jobs failed on setup problems: 15 lost their artifacts
to an upload defect and one failed in dependency bootstrap. The 48 Node, PHP and
Python correctness, compatibility, methods and timing cells never ran: the phase
gate starts them only after the Dart and browser jobs of the same phase
succeed, and those failed. Those profiles are unknown, not failed.

## Where the record lives

The research is frozen in the Git tag `archive/rl00-no-go`, which points to
commit `d3e1fe3`. These pages hold the details.

- [Design](https://github.com/mikhailsal/ai-boilerplate/blob/d3e1fe3bd505c513c0942766229b69a9ea8fafd7/docs/plan/test-resource-limits.md):
  the owner's boundaries, the architecture and the work sequence.
- [Per-test budgets](https://github.com/mikhailsal/ai-boilerplate/blob/d3e1fe3bd505c513c0942766229b69a9ea8fafd7/docs/plan/test-resource-limits/per-test-budgets.md):
  the case subject, the selection research direction and the required proofs.
- [RL00a remote evidence](https://github.com/mikhailsal/ai-boilerplate/blob/d3e1fe3bd505c513c0942766229b69a9ea8fafd7/docs/plan/test-resource-limits/rl00a-remote-evidence.md):
  the 26-pair containment matrix.
- [Campaign evidence](https://github.com/mikhailsal/ai-boilerplate/blob/d3e1fe3bd505c513c0942766229b69a9ea8fafd7/docs/plan/test-resource-limits/rl00bc-evidence.md),
  [recommendation](https://github.com/mikhailsal/ai-boilerplate/blob/d3e1fe3bd505c513c0942766229b69a9ea8fafd7/docs/plan/test-resource-limits/rl00bc-recommendation.md)
  and [outside review](https://github.com/mikhailsal/ai-boilerplate/blob/d3e1fe3bd505c513c0942766229b69a9ea8fafd7/docs/plan/test-resource-limits/rl00bc-review.md):
  the results, the classified outcomes and the audit.
- [Receipts](https://github.com/mikhailsal/ai-boilerplate/blob/d3e1fe3bd505c513c0942766229b69a9ea8fafd7/docs/plan/test-resource-limits/rl00bc-receipts.json)
  and [timing samples](https://github.com/mikhailsal/ai-boilerplate/blob/d3e1fe3bd505c513c0942766229b69a9ea8fafd7/docs/plan/test-resource-limits/rl00bc-measurements.json):
  the SHA-256 binding to the CI artifacts, which expire after one day, and the
  samples behind the decisive result.
