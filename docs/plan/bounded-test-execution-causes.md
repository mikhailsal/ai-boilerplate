# Bounded test execution: why no solution has been found

Status: written on 2026-11-09 as part of the close-out of RL00. It continues the
[problem statement](bounded-test-execution.md) and precedes the
[directions](bounded-test-execution-options.md). Each cause separates what the
research showed (Evidence) from what is inference (Hypothesis). Hypotheses were
not tested and must not be quoted as findings.

## Why the problem is hard

1. **Certifying a case needs isolation, and isolation pays a start-up per
   case.** The contract wants the time and the kernel-charged memory of one
   case, with its setup, teardown and children, independent of order and
   neighbours. The only method that gave an unambiguous number was a fresh
   subject per case: runtime start, imports, collection, setup, call and
   teardown. Evidence: in the browser corpus the instrumented canonical run
   matched the native median, while eight fresh probes took about two seconds
   each and added 14.4 to 17.8 s per sample. Under criterion A the corpus could
   add only about 5.5 to 6.4 s over the native p95, roughly 0.7 to 0.8 s per
   probe, if the instrumented run costs what the native one does. Hypothesis:
   the overhead grows with cases times start-up cost, while native time grows
   with the work done, so larger suites fare worse; the large corpus never ran.

2. **Cheaper methods lose attribution.** In a shared worker, lifetime peaks mix
   cases, resident-size differences depend on allocator reuse, and the kernel
   leaves a charge with the group that allocated it. Shared mappings and warm
   caches are charged to whoever touched them first. The archived contract
   already names resident-size deltas, worker peaks, moving a reused worker and
   forking preloaded state as insufficient on their own. Evidence: the
   shared-worker arm was recorded as unsupported, and the browser `child` case
   could not be attributed to an allocation phase. No cheaper arm proved that it
   can certify a case.

3. **Selecting which cases to probe is unsolved in general.** Only selection
   avoids probing every case, yet a case's cost can change through source,
   fixtures, data, dependencies, runtime or configuration while its text stays
   the same. The contract therefore asks for proof of influence and widens to the
   whole relevant suite on any doubt, and first adoption always widens.
   Evidence: the selection fixtures were finite, and narrow selection cost was
   not measured. Consequence: the fallback arm is what every new project meets
   first, and it is the arm that failed. Hypothesis: the usual coverage-based
   change-impact methods are heuristic at their edges (data files, environment,
   dynamic dispatch), and a persisted impact map needs owner approval that the
   plan did not give.

4. **Memory is not one number.** The kernel charges page cache, temporary
   files and shared mappings, a hard limit can be overshot briefly, and reclaim
   and writeback depend on host state. Evidence: a writer overshot its ceiling
   by 4 KiB, residual charges after a kill were sometimes nonzero, and the cache
   fixture needed an owner-approved split into dirty-cache containment and
   successful reclaim after two CI failures. Consequence: every per-case norm
   rests on accounting conventions that must be chosen, documented and
   defended, and the plan chose no numerical defaults.

5. **The proof burden multiplies.** Five profiles, two architectures, two
   provisioning paths, several corpus sizes, lifecycle, races, faults, selection
   and adoption each needed an oracle and labeled examples. Evidence: the
   risk-first order ran Dart and browser first, and the phase gate then skipped
   the Node, PHP and Python cells. Hypothesis: those runtimes start faster than
   a browser, so a different order might have found a passing profile before a
   failing one ended the campaign.

6. **The foundation has an open gap.** The contract requires cleanup that does
   not depend on the launching process, and a late sweep on the next invocation
   does not count. Evidence: after SIGKILL of the requester, no automatic
   cleanup was observed in four of four cells, the mechanism is unattributed and
   the recovery from abrupt guardian and controller death never ran. Until this
   closes, even the containment half of the problem is not finished.

7. **Fail-closed protection needs an environment that may not exist.**
   Delegated cgroup v2 exists only on Linux, may need administrator preparation
   and is often missing in containers and constrained agent sandboxes
   (hypothesis; no environment survey was made). Because an unsupported host
   starts no payload, every missing prerequisite blocks a contributor.
   Evidence: the Python overlay took 94 to 138 s to the first protected own test
   without administrator wait. Administrator wait, missing delegation and
   novice usability were never measured.

8. **The experiments were expensive.** All heavy work ran in CI by the owner's
   instruction. The harness grew to 81 files with 16,282 added lines under the
   acceptance tests, plus three workflows. Evidence: an artifact upload lost 15
   Dart artifacts over a colon in a file name, and a verdict-mapping defect
   turned complete records red; neither was found by the static review, and each
   needed a full CI cycle to expose. This is a process lesson more than a
   technical limit, and it argues for smaller experiments.

## How the causes interact

The requirements pull against each other in pairs.

- Per-case certification against low overhead: certification wants a fresh
  subject, overhead wants a shared one.
- Early detection against sound selection: detecting a costly case when it is
  added needs selection, and sound selection needs a trusted influence map or a
  full fallback.
- Fail-closed locally against easy onboarding: a missing prerequisite blocks
  work instead of degrading it.
- One contract for five profiles against five execution models: a process per
  case is natural in Python and PHP, but Node workers, Dart isolates and
  browser pages share more state.

A solution probably has to relax one requirement or solve one sub-problem in a
different way. The directions page lists the candidates and what each would
cost the owner.

## What is not known

- What a browser probe spends its two seconds on. Build, server start, browser
  launch, collection and the test body were never separated.
- How the Python, PHP and Node profiles perform, and whether any of them passes
  criterion A with fresh probes.
- The cost and soundness of narrow selection, and how often real changes would
  force the full fallback.
- How a per-file or per-worker subject compares with a per-case subject on
  real agent-written suites.
- How long onboarding takes with real administrator wait and missing
  delegation, and whether a novice can act on the verdicts.
- Why cleanup did not happen after SIGKILL of the requester.
