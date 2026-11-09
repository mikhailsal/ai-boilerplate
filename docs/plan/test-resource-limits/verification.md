# Test resource limits: verification gates

Status: owner D4 research amendment accepted on 2026-11-04; affected
engineering re-review and final owner plan approval completed on 2026-11-06.
RL00a is technically complete within the limits of the [final remote evidence](rl00a-remote-evidence.md);
earlier failed CI observations remain recorded. RL00b and RL00c ran in part on
2026-11-09; the [recommendation](rl00bc-recommendation.md) is no integration,
and the owner's next decision remains pending. The owner selected D5=A on
2026-11-06. Plan approval did not itself authorize execution; subsequent owner
instructions authorized the recorded experiments and require future heavy checks
in CI. Current-task commit and push hook skips were explicitly permitted without
changing installed hooks. Merge and product integration are not authorized.
Missing required evidence is no-go, not permission to substitute aggregate-only
or unbounded certification.

## Sequential feasibility and integration

Before experiments, preregister expected verdicts for session fixtures,
reusable browser/runtime setup, teardown, parameters and child services;
distinguish standalone and canonical accounting and compare methods on the
same examples. Bound stress sizes before running.

1. **RL00a:** define subjects and verdicts; prove kernel containment,
   provisioning, pre-exec placement, supervisor survival and death/cleanup on
   ordinary-host and prepared-subtree paths. Record overshoot and cleanup
   latency; unresolved required guarantees go to the owner or no-go.
2. **RL00b:** investigate selective strict checks first, comparing full
   standalone and shared-worker instrumentation under identical verdicts. Prove
   affected-input selection and full relevant-suite fallback for unknown influence
   or first adoption; cheap signals cannot certify individual compliance. Compare
   accounting methods for every profile, starting with Dart and browser,
   then PHP and Python.
   Cover shared fixtures, parameters, owned children and parallelism; prove
   nested capacity and canonical semantic compatibility. Unsupported required
   attribution is no-go.
3. **RL00c:** measure labeled verdict usefulness, native/protected overhead,
   churn and fresh-export/update onboarding. Stop if owner-reviewed useful
   verdict or checker cost criteria fail. Developer-host and real GitHub Ubuntu
   evidence are required; concrete CI/setup changes and workflow SHA must be
   reviewable and separately approved before the live GitHub proof.

Only a successful RL00 go/no-go record permits considering RL01–RL06: policy,
migration and setup; hierarchy and case evidence; all adapters and browser
ownership; real hooks, nesting and export; reports, calibrated values and
documentation; then full validation and handoff. Shared model/lifecycle work
precedes disjoint adapter work; hook/export/CI acceptance follows all required
profiles. Each slice includes coherent code, tests and docs. Retained spike
artifacts meet existing quality, size and layer rules, or are discarded; no
special bypass, exception or automatic threshold increase is granted.

## Required proofs

Each new test needs an observable regression and an explicit limit on its
claim. Extend existing boundary tests where appropriate. No model evaluation
suite or test retirement is introduced. Retain CP1-CP10/EC1-EC10 and extend the
existing boundary tests with CP11-CP12/EC11-EC13 below.

| Proof | Required observation and limit of claim |
| --- | --- |
| CP1 | Preview and execution resolve identical staged/revision policy and ancestors; invalid or missing policy starts no tests. Mocks do not prove kernel enforcement. |
| CP2 | Both provisioning paths enable empty branches top-down and place payload before exec; partial setup launches nothing. One host does not prove all matrix rows. |
| CP3 | One costly case fails below aggregate ceilings; cheap additions, order and worker assignment cannot hide or transfer its cost. Only the declared subject is certified. |
| CP4 | Two nested levels retain ceilings, deadlines and capacity; impossible allocations fail promptly. This is not a hostile same-UID sandbox proof. |
| CP5 | Interrupt, timeout and control death clean owned detached descendants by the approved deadline on both paths; unrelated runs survive. Uninterruptible kernel states need explicit disposition. |
| CP6 | IDs, parameters, variants and resources survive transforms; retry, expected failure and quarantine cannot erase violations. Synthetic reports do not prove native producers. |
| CP7 | Canonical coverage and scenario outcomes remain valid; probes cannot substitute canonical coverage/scenario evidence or hide skipped work. Fixture parity covers recorded examples only. |
| CP8 | First-adoption and unknown-influence selection expands fully; real hook/export/update flows reject costly test, source, fixture, data, parameter, dependency, runtime and configuration edits; export fences and historical core contracts hold. Live GitHub proof needs separate authorization. |
| CP9 | Text and JSON preserve safe identity, subtype, cause, action and cleanup state; stdout stays clean and secrets are redacted. Golden examples do not cover every OS fault. |
| CP10 | Preregistered ordinary, excessive and justified cases yield useful verdicts; interleaved native/protected cost and full-clock onboarding meet owner-reviewed criteria. Arbitrary host contention cannot be made deterministic. |
| CP11 | Test, source, fixture, parameter, data, dependency, runtime and config edits select all affected cases; initial adoption or unknown influence expands fully. Synthetic dependency graphs cannot prove arbitrary dynamic influence. |
| CP12 | A bounded candidate/policy/runtime/identity-bound scope record requires strict evidence for every selected case and keeps canonical success separate. Record integrity does not prove selection soundness or kernel enforcement. |

| Edge | Required observation and limit of claim |
| --- | --- |
| EC1 | No-suite checks and preview start no session; an empty mandatory selected suite still fails `tests.none`. This does not prove memory enforcement. |
| EC2 | Reject missing, empty, wrong-type, nonfinite, overflow, unlimited or above-ancestor limits; validate and preview agree. Schema tests do not prove kernel interpretation. |
| EC3 | Migrated workers, persistent allocations, fork state, shared mappings, warm caches and retained services cannot appear free. Unaccountable subject means unavailable/no-go. |
| EC4 | Suite exhaustion with cases below their own ceilings is a suite violation with unknown case; external kills do not invent a culprit. Event replay cannot replace live exhaustion. |
| EC5 | Caught own denials fail; reclaim and throttling alone do not. A nested negative probe fails its own run without falsely poisoning ancestors. Event patterns need kernel-specific proof. |
| EC6 | Concurrent parent workers requesting children stay bounded, fail impossible allocations without cycles, and release state on cancellation/death. No cross-project scheduling is claimed. |
| EC7 | Both launch/cleanup orders preserve ownership; stale or replayed paths, namespace views and partial setup cannot authorize foreign cleanup. Drift detection is not hostile-attacker defense. |
| EC8 | Missing, duplicate, stale, truncated or unknown evidence fails; oversized reports and post-native hangs remain bounded without erasing causes. Replay is not native reporter proof. |
| EC9 | Tempfiles, tmpfs, residual charges and dying groups are cleaned or reported within approved bounds; prior charges are never reported as zero. Corpus size and bounds are preregistered. |
| EC10 | Monotonic deadlines specify suspend behavior and reserve cleanup; concurrent OOM, timeout and SIGINT retain proven causes and incomplete cleanup. Injected clocks cannot prove arbitrary kernel scheduling latency. |
| EC11 | Missing selected identities and unexpected parameter/browser variants widen within remaining budgets or fail; previous breaches remain failures. Reporter replay cannot replace native profile proof. |
| EC12 | Untrusted comparison inputs, candidate drift, policy/runtime mismatch or stale scope cannot enable narrow verification. No verdict cache or reset deadline is introduced. |
| EC13 | Absence of cheap duration/memory/event signals cannot bypass strict evidence for a selected case. One trigger fixture does not prove complete influence analysis. |

## Profiles, measurements and onboarding

Maintain a support matrix for supported Linux hosts, prepared containers,
GitHub runners and constrained agent environments. For each row record
controllers, permissions, writable subtree, kill support, user-manager/runtime,
privilege needs, partial-setup recovery and time to first protected test.
Unsupported test-scheduling environments fail closed. Inventory and provision
contributors and CI before rollout; re-probe on kernel/runner changes. The
template CODEOWNER owns compatibility maintenance and atomic core/policy
rollback. Doctor's read-only capability probes do not claim an OOM experiment;
bounded live proof is separate. Quality never self-escalates privileges.

For every profile and suite kind, compare representative small and larger
suites using interleaved native and protected runs. Record extra wall and CPU
time, peak memory, tasks, collection, startup, fixture reuse, coverage mode,
workers, runtime versions and environment conditions. Include selection cost,
fallback frequency and total runtime after broad source/dependency changes and
first adoption; do not report only the cheap selected-case path. Measure fresh runtime
and group creation, dying groups, residual charges and private tmpfile/tmpfs
cleanup. Reuse caches only when compatible with the declared subject; never
cache resource verdicts or reset reused peaks as fresh.

Calibrate fixed norms against labeled ordinary, intentionally excessive and
justified expensive cases, recording expected and observed verdicts and host
noise. The owner reviews headroom, numerical values and the overhead release
criterion. Exported-project calibration uses finite reviewed provisional hard
limits including case protection; it neither permits unbounded measure-only
success nor writes norms automatically. Complete fresh-export and update trials.

The first-use clock begins at a fresh supported checkout/export and includes
reading, bootstrap, downloads and cache state, delegation preparation, active
work and administrator wait through the first understood protected own-test
result. Record total, active and wait separately, along with capabilities,
versions and whether users identify the effective budget and reason. Under five
minutes is a provisional target, not a measured result. Verify prepared-host
and administrator-required paths, safe recovery, preview parity, redaction and
text/JSON examples in real acceptance flows. Documentation and diagnostics
must accompany implementation, including setup, migration, rollback, policy,
accounting, support and rule-ID troubleshooting.

Before method comparison, preregister the charged-memory quantity, swap
semantics, per-profile execution-model/certifying-arm matrix and expected
unsupported cells. Extend CP2/CP5/EC7/EC10 for mount/ancestor visibility, opaque
names, symlink escape, threaded placement and namespace-aware ancestor deadlines.
Extend CP3/EC3/EC5 with retained allocator pages, successful cache reclaim and
native/child allocations. Extend CP9/CP10 with checker-capacity nonpasses,
preserved actual ancestor violations, and wall-time/throttling context.
Selection fixtures include staged/revision/CI bases, data/volatile inputs and
full canonical CI coverage. No assumed average startup floor proves admission.

The comparison report records machine/runtime, corpus size, sample count,
interleaved native/protected runs, distributions including p50/p95, pathological
and steady-state cases, and whether reproduced on main. No samples or performance
improvement are claimed today. Current quality and coverage rules apply to
retained artifacts; real delegated proofs cannot be replaced by fake cgroupfs
assertions or by merging unrelated coverage into the unit floor.
