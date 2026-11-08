# RL00b/c: subjects, corpus and bounded proof contract

Status: preparation only; no native B/C experiment has run. The
[experiment protocol](rl00bc-protocol.md) owns execution approvals,
measurement criteria and adoption. This linked contract preserves the
subjects, native corpus, proposed bounds and selection proof that must
be frozen with the protocol before an approved live run.

## Subjects and memory quantity

The enforced quantity is cgroup-v2 kernel-charged memory of the declared
subject and descendants. Swap is disabled for each experimental subtree.
This is not a measurement of all physical resident pages: immutable runtime
files, shared mappings and existing cache charges require explicit scope and
shared-cost records. Record unavailable categories rather than invent zero.

A fresh strict subject starts before the native runtime, imports, collection,
fixture setup, call, teardown and owned children. Browser subjects additionally
include the production build and owned preview/browser processes. Controller
and materialization work have separate finite capacity inside the invocation;
their cost remains in the protected-arm total. Canonical native execution
remains the authority for coverage and scenarios. A successful strict probe
does not replace canonical evidence.

Shared-worker instrumentation reports the worker lifetime, boundary samples
and actual native identities. It may certify a case only where the complete
declared cost can be attributed. A lifetime peak, RSS difference or runtime
heap counter alone is not such proof. Migration of an already charged worker
must not be presented as fresh case accounting.

## Required execution models

| Model | Native producer | Cases and variants | Shared costs to retain |
| --- | --- | --- | --- |
| Dart VM | package:test JSON and branch coverage | Native test IDs and parameter names | VM, collection, suite fixture, retained allocations |
| Node unit | Vitest native report and V8 coverage | Native file/test/parameter identity | Worker/runtime and suite fixture |
| Browser | Playwright native JSON, projects and traces | Case plus desktop/mobile project | Build, production server, browser and worker |
| PHP | PHPUnit JUnit, Clover and Xdebug data | Native test and data-provider identity | Runtime, class setup and autoloader |
| Python | pytest JUnit, collection and coverage.py | Native node ID and parameter identity | Imports, session fixture and workers |

Use the repository's actual locked SDK/packages and fixed supported system
prerequisites. Record actual versions; a directory name alone is not a version
probe. Bootstrap fills caches but does not retain all helper installations.
Prepare dependencies offline from the locked manifests in a separate bounded
remote phase. Missing cache or runtime support is a setup nonpass, not evidence
that a test exceeded its norm. Do not install an unpinned substitute.

Compare the same examples in three arms: full fresh standalone cases;
selective strict cases plus canonical execution; and shared-worker
instrumentation. Dart/browser are evaluated first, then PHP/Python/Node.
Native serial-only capabilities remain serial; no invented parallel runner.

## Corpus and expected verdicts

Materialize a four-case small corpus and a sixteen-case larger corpus per
unit execution model. Browser projects retain both viewport variants, so the
native variant count can be greater. Record discovered and expected sets and
reject missing, duplicate or unexpected identities. Keep native outcome and
strict resource verification in separate fields.

Dart and Node unit cases are partitioned across two real test files without
changing their unique native names. Instrumented two-worker trials require
reciprocal readiness and acknowledgment events from distinct native workers;
Dart uses isolate identities and causal handshakes rather than comparing
different Stopwatches. Phase events retain actual native identifiers where
available, owned-child readiness/membership and real local memory-event counters.
Unavailable fields remain unavailable. Partial Dart starts are retained only
after a separately proven resource stop; canonical success still requires a
complete successful producer report.

Interrupted Dart streams retain every observed test start, its run-local numeric
ID, source, error state and explicit visible/hidden/unknown status. Only a
completed hidden success or skip can be excluded from visible-case cardinality.
Unexplained competing starts, a focused stream or a truncated tail leave strict
selection unproved while preserving the raw kernel resource cause. Cross-run
binding compares actual corpus-relative source and native name; numeric test IDs
are never assumed stable across runs. Retained fixtures are partitioned by
actual worker and source/project context, including distinct files in a reused
Node fork. Their shared costs remain separate from individual case attribution.

Case-event bridges additionally require an exclusive native identity and one
emitter in a valid bounded event-file set. Unknown, malformed or oversized files
cannot be dropped to manufacture uniqueness. Resource attribution uses actual
entry and end counters; a completed phase with no counter growth cannot inherit
a later OOM. An interrupted open phase ends at the kernel stop observation only
when no later fixture phase was observed. Shared comparisons retain selection
validity, canonical case completion and cleanup requirements without assigning
their retained allocation to an individual first consumer.

| Example | Canonical expectation under the suite envelope | Strict expectation |
| --- | --- | --- |
| Ordinary call | Native success | Success without resource events |
| Private native allocation | Native success below suite ceiling | Own-case violation at the smaller case ceiling |
| Expensive setup or teardown | Native success | Violation retains its actual phase and subject |
| Owned allocating child | Native success | Child remains inside the case's enforced scope |
| Shared retained fixture | Same functional result across order | Shared cost visible; no first-consumer blame |
| Cheap/heavy parameters | Distinct native identities | Heavy variant cannot disappear in normalization |
| Slow bounded call | Native success within suite time | Case deadline violation with complete cleanup |
| Explicit justified class | Native success | Success only under its separately declared allowance |
| Cheap additions and reordering | Same native results | Cannot dilute or transfer an existing breach |
| Unavailable shared attribution | Native result recorded | Explicit nonpass, never individual compliance |

Use real producer reports and source exercised by native coverage. Run actual
scenario reconciliation and compare canonical identities/results, coverage
and fixture behavior. Native success, a report file or a synthetic marker is
insufficient to establish this parity. Failure to implement a required oracle
is unfinished work, not a demonstrated no-go.

Correctness pressure runs use one expensive target at a time and one native
worker. Separate bounded ordinary/reordering trials exercise native workers
one and two where supported, concurrent strict subjects, deterministic nested
shares, rejected impossible child allocations and cancellation recovery.
Every expected own/ancestor event is declared before launch. An unknown
external kill never invents an offending case.

## Proposed finite experiment bounds

These are experimental capacity bounds, not production policy defaults.
Their final values and capability rows must be frozen before execution.

| Boundary | Proposed finite allowance |
| --- | --- |
| Per-profile service | 4096 MiB, swap zero, 512 tasks, 45-minute lifetime |
| Controller/guardian reserve | Within that total; separately capped and recorded |
| Runtime identity probe | 512 MiB, 64 tasks, twenty-second native allowance per command, within the original enclosing deadline |
| Lifecycle proof subject | Finite requested caps within the work branch; sixty-second native allowance, clamped to the original ancestor deadline; above-capacity requests execute no payload |
| Nested proof | Two 512 MiB/64-task domains; each has a 128 MiB/8-task parent leaf and a 320 MiB/40-task child pool; sixty-second enclosing proof bound within the original deadline |
| Fault proof | Sixty-second enclosing bound; 128 MiB/8-task native leaves; lower task cap only to seven; membership target separately reserved at 128 MiB/8 tasks; unassisted cleanup window at most three seconds |
| Selection-pressure proof | Sixty-second enclosing bound; 72 MiB touched input; canonical 256 MiB/16 tasks versus strict 48 MiB/8 tasks; ten-second native allowance within the unchanged ancestor deadline |
| Canonical suite subject | 3072 MiB, 256 tasks, 90-second native allowance |
| Python/PHP fresh subject | 384 MiB, 128 tasks, five-second native allowance |
| Node fresh subject | 768 MiB, 128 tasks, five-second native allowance |
| Dart fresh subject | 1024 MiB, 128 tasks, five-second native allowance |
| Browser fresh subject | 1536 MiB, 256 tasks, twelve-second native allowance |
| Explicit justified class | The profile's fresh-subject memory cap plus 512 MiB, at most 3072 MiB; fixed justification and exact subject required |
| Intentional native allocation | At most 1536 MiB, touched and bounded; one target at a time |
| Shared fixture | At most 128 MiB; recorded separately, proposed ordinary value 64 MiB |
| Slow target | Eight seconds for unit models, twenty seconds for browser |
| Cleanup reserve | Three seconds within the original enclosing deadline |

Reject a request above ancestor capacity before launching it. Each run has one
absolute enclosing deadline; creating a subject, expanding selection or
retrying cannot restart it. Independent provider cleanup must survive the
controller's death. Record native status, own and ancestor event baselines,
CPU/wall time, task count, memory peak availability/samples, kill/empty/root
removal observations and remaining charges. Do not claim immediate zero
charges, exact deletion instants or universal scheduling bounds.

## Selection proof

Bind the invocation-local scope to candidate/base/tested trees, policy bytes,
runtime/package inputs, discovered native IDs/variants, changed inputs and
selection/fallback reasons. Preserve existing staged, revision, push, merge
and queue comparison semantics. Do not persist impact maps or resource verdicts.

Exercise actual mutations of tests, source, fixtures, parameters, data,
dependencies, runtime and configuration. Also exercise first adoption,
deleted/renamed cases, unexpected variants, unknown dynamic influence,
volatile input, untrusted comparison and candidate drift. Unknown influence
or first adoption expands to the full relevant suite or fails. A static toy
dependency map cannot prove arbitrary dynamic influence. No absence of cheap
signals grants individual compliance. Preserve the failure if a later wider
check supplies more evidence.

Candidate observations use actual core snapshots, fresh native discovery and
Git tree changes for each mutation, including deletion and rename. Narrowing
is limited to the finite fixture's explicitly independent files; it does not
prove arbitrary project influence. Unknown or untrusted comparisons expand
fully. Scope-binding observations do not certify strict resource execution or
real hook/export rejection.
