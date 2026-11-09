# Bounded test execution: directions for a solution

Status: written on 2026-11-09 as the last part of the RL00 close-out, after the
[problem statement](bounded-test-execution.md) and the
[causes](bounded-test-execution-causes.md). The directions are hypotheses for a
later attempt, not findings. Apart from facts cited from the archived research,
nothing below was measured. A new attempt needs its own protocol, a frozen
commit and explicit owner approval.

## What the evidence suggests

- The decisive failure, the overhead, came from one choice: a fresh probe per
  case as the certifying method. Instrumenting the canonical run cost almost
  nothing, so the requirements are not shown to be too expensive as such.
- Certification and attribution are different jobs. A method can show that no
  case exceeded a bound without naming a culprit, and naming one can be paid
  for only when a bound is breached.
- Time and memory aggregate differently. Time adds up over the cases of a
  worker, which runs them one after another and which the runners already time
  per test. Peak memory and peak task count behave like a maximum. This is a
  hypothesis to verify per runner.
- The subject need not be a case. A file, a worker or a shard is a coarser
  subject, and runners already isolate it.

## Directions

### A. Bound the shared worker, diagnose on breach

Run cases in workers whose cgroup has a hard memory and task cap. Group them by
budget class, so that cases with a justified allowance share a worker only with
each other. Measure time per case inside the canonical run and keep the native
per-test timeouts. Hypothesis: the memory charged to a worker at any instant
includes everything the running case holds, plus the runtime baseline and the
leftovers of other cases. A worker that never reached its cap therefore proves
that no case in it needed more than the cap. Adding cheap cases or reordering
cannot hide a heavy case from the cap, and the kernel enforces the cap at almost
no cost.

The price is false alarms and anonymity. Retained memory, fragmentation and
lazy garbage collection can fill the cap without any heavy case, and the cap
names no culprit. Both are resolved on the failing path only, by bisecting the
worker's cases or probing the suspects freshly. Group size is a dial: one case
per fresh worker is the measured design, and the whole suite in one worker is
the cheap end. The archived contract allows cap compliance without an exact
peak where proved. RL00's shared-worker arm reported lifetime evidence and
boundary samples and was judged on attribution; the upper-bound argument itself
was not tested.

- Main risks: memory charged to another group, such as shared page cache, is
  invisible; garbage-collected runtimes (Node, Dart, browsers) may fill any cap
  lazily; grouping changes parallelism and fixture reuse.
- First experiment: Python only. Run a labeled corpus of ordinary, excessive,
  justified, retaining, child-process and lazily importing cases in reordered
  and padded orders. Require no missed excessive case and count false alarms.
- Owner decision: whether a proved upper bound counts as certification, since
  decision D4 rules out cheap signals as proof. The weaker variant keeps only
  invocation and worker caps and reports per-case memory as advice, which
  reopens decision D2, the mandatory per-case memory outcome.

### B. Fork server per runtime

Warm a runtime once, then fork a child per case into its own leaf cgroup. The
leaf is charged for the child's own copy-on-write and new allocations, and the
warm baseline is paid once. This suits Python and PHP, not Node, Dart or
browsers.

- Main risks: fixtures that do not survive a fork (threads, sockets, event
  loops), coverage merging, and the charge rules for pages shared with the
  parent.
- First experiment: a Python-only plugin spike that compares per-case cost with
  fresh probes on the labeled corpus.
- Owner decision: per-profile guarantees (see the order below).

### C. A coarser subject

Use the boundary a runner already isolates, such as a file, a worker or a
shard, as the subject. Every run measures every subject, so no selection and no
influence analysis are needed.

- Main risks: an expensive case hides inside a large file's budget.
- First experiment: on the labeled corpus, count how many excessive cases a
  file-level budget still catches.
- Owner decision: whether the case remains the subject.

### D. Cheaper fresh probes

Make the probe itself cheaper: charge a shared build and server once, keep a
warm browser pool, and use start-up snapshots where a runtime has them. Under
criterion A the browser probe would have to fall from about two seconds to
about 0.7 or 0.8 seconds.

- Main risks: sharing weakens the isolation that made probes certain.
- First experiment: split the browser probe into build, server start, browser
  launch, collection and test body. If no part can shrink enough, stop.
- Owner decision: none for the measurement itself.

### E. Sound change-impact selection

Record which source each case touches during the canonical run, for example
with per-test coverage contexts, and treat anything outside the map as unknown,
which widens to the full relevant suite. Selection lowers the number of probes
but never removes the first-adoption fallback.

- Main risks: data files, environment and dynamic dispatch escape the map, and
  a persisted map is a new trust mechanism that the plan did not approve.
- First experiment: replay this repository's history with injected cost and
  measure how often the map misses an affected case.
- Owner decision: approve a persisted impact map, or recompute it in every run.

### F. Enforce at the platform boundary

Apply container, job or systemd limits around the agent sandbox and CI, keep
the native timeouts, and let the gate document a reference recipe and warn when
it detects no limit. This needs no cgroup machinery in the gate and works on
every profile.

- Main risks: protection is weaker locally and depends on the platform, and the
  gate cannot name an expensive case.
- First experiment: test the recipe on the CI runners and one agent sandbox.
- Owner decision: relax fail-closed locally to a warning.

### G. Advisory telemetry first

Report the slowest cases and, where measurable, the most memory-hungry ones
from the current run only. The approved scope already lists optional suite
rankings (SLOW-01 and MEMORY-01) and excludes historical storage and regression
ratchets. Real data would show how agent-written suites behave before any
threshold is enforced.

- Main risks: nothing blocks a bad test, and the normalized case result keeps
  no timing today, so the reports need that change first.
- First experiment: keep per-test durations in the normalized results and
  inspect this repository's own suites.
- Owner decision: none beyond the approved scope.

### H. Close the foundation gap

Attribute why nothing was cleaned up after SIGKILL of the requester, and run
the guardian and controller death cases that never ran. Every direction that
bounds an invocation needs this, and none of the others replaces it.

## Suggested order

1. Facts first, with no enforcement: attribute the cleanup gap (H), keep
   per-test durations in reports (G) and split the browser probe cost (D). Gate:
   a short report to the owner.
2. One spike on one profile. Python with direction A; if it misses an excessive
   case or raises too many false alarms, try B. Preregister the labeled corpus,
   the pass bar and the overhead criterion for both the failing path and first
   adoption before any run. A direction stops when its first experiment
   contradicts its key assumption.
3. Owner gate. With data, choose which requirement to relax: D2, the case as the
   subject, fail-closed locally or the overhead criterion. Record the
   amendment before the experiment that depends on it, never after seeing
   results.
4. Widen to other profiles one at a time. A profile that fails stops with
   evidence, as the archived plan already requires.

## Lessons for the next attempt

- Pair risk-first with value-first: try the profile most likely to pass next to
  the hardest one, and do not let one profile's failure skip the others.
- Decide in advance whether the first-adoption fallback must meet the overhead
  criterion, because every project meets it first.
- Prefer a small spike with one falsifiable question to a large preregistered
  matrix. Keep the harness small and unit-test its verdict mapping and artifact
  names before the live run.
- Keep the evidence that decides the result beyond the one-day artifact
  retention.
- Name the owner decisions a result depends on before producing it.

## Owner decisions a new attempt needs

1. Whether per-case memory certification stays mandatory (D2), or an upper
   bound or an advisory report is enough.
2. Whether the subject is a case, a file or a worker.
3. Whether protection fails closed locally or only in CI.
4. Whether first adoption must meet the overhead criterion.
5. Which profiles are in scope, and whether a profile may ship with a lower,
   explicitly stated guarantee.
6. Whether a persisted impact map is acceptable.
