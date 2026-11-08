# RL00b/c: preregistered method and adoption experiments

Status: preparation only. The owner requested completion of RL00a, RL00b and
RL00c and an evidence-based integration recommendation on 2026-11-08. This
page records a proposed experiment before measurement. It does not claim an
executed comparison, accepted numerical criteria or production protection.
The [verification contract](verification.md) and [per-test contract](per-test-budgets.md)
remain binding. All heavy execution is remote in CI; the developer's machine
must not run the native workloads, bootstrap, quality suites or stress cases.

## Decision and execution gates

RL00a's final evidence is recorded in [the remote report](rl00a-remote-evidence.md).
Its source revision remains an immutable baseline. These experiments do not
modify its payloads, budgets or historical observations.

Before a native experiment, freeze this protocol, its corpus, expected
verdicts, tool/package inputs, controller source, finite bounds and workflow.
Retain Git revision, tree, source bytes and SHA-256 inputs with every result.
The owner reviews the numerical release criteria and concrete workflow before
the live proof. Preparing files or running normal CI is not that approval.
The current task's explicit local hook exception remains scoped to commit and
push; installed hooks and their configuration are unchanged.

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

## RL00c measurement and proposed release criterion

Separate correctness pressure from the ordinary performance corpus. Interleave
native and protected runs of each identical small/large corpus and supported
suite kind. Preregister twenty valid samples per comparison cell; retain all
attempts and setup failures. Report empirical p50/p95 and the full samples,
not a population bound or a claim of precision beyond this corpus. Do not retry
to obtain a green result or discard a costly valid sample.

Include collection, startup, shared setup, teardown, controller/selection cost,
CPU time, wall time, memory/tasks, coverage mode, workers and actual environment.
Measure narrow changes, broad source/dependency changes, full fallback and
first adoption. Record residual charges, churn/dying groups and temporary-file
and tmpfs cleanup. Reuse compatible package caches, never resource verdicts.

Proposed criterion A for owner review: all labeled verdicts and required
identity/scope/cleanup checks are correct, with no false compliant result;
for every required ordinary comparison, protected p95 wall time is at most
twice native p95 plus two seconds, including fallback/adoption, and all work
fits its finite envelope. Unsupported required attribution is no-go. This
criterion is a proposal, not an accepted threshold or measured result.

An alternative stricter criterion is 1.5 times native p95 plus one second.
Changing the criterion after looking at results requires a recorded amendment
and a separately identified evaluation; it cannot relabel the original result.
Only an owner-reviewed stop rule can terminate a later matrix after a decisive
required failure. Unrun cells remain explicitly unrun.

## Adoption and environments

Time fresh export and update from a fresh supported checkout through the first
understood protected own-test result. Record downloads/cache state, preparation,
administrator wait, active time and total separately. Exercise prepared and
administrator-required provisioning, missing delegation, safe failure and
matched rollback. The sub-five-minute onboarding target remains provisional.

The current product/export has no resource-policy integration. Distinguish
real native export/update behavior from an explicitly identified experimental
overlay; an overlay cannot prove that unmodified hooks or exported projects
already enforce the new contract. Required preview/migration/protection claims
need real exercised code or remain unproved.

Use real GitHub Ubuntu execution plus an honestly described remote
developer-host-equivalent environment. Do not label GitHub-only observations
as measurements on the owner's machine. Prepare a capability matrix including
the retained x86_64/aarch64 glibc support boundary and unsupported rows; a
single architecture cannot prove all rows. Any unavailable required host row
must be resolved or included in the no-go recommendation.

The proposed remote matrix includes `ubuntu-24.04` and `ubuntu-24.04-arm`.
GitHub documents both as standard public-repository VM labels; capture actual
architecture, kernel, memory and delegation rather than treating the label as
proof. See [GitHub's runner reference](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job).
Playwright selectors must account for its combined project/file/title matching,
then validate the emitted exact identity and project; see the [pinned selector contract](https://github.com/microsoft/playwright/blob/v1.64.1/docs/src/test-api/class-testproject.md).

## Final recommendation artifact

Produce a requirement-by-requirement report with raw-source/artifact binding,
method/support matrix, actual verdicts, parity and selection proofs,
measurements/distributions, adoption evidence and limitations. Distinguish
proven failure, unsupported attribution, setup failure and unperformed work.
Recommend integration only if the complete required contract and approved
cost/usefulness criteria pass. Otherwise recommend no integration and identify
the evidence-backed reason and required next decision. RL01-RL06 production
implementation and merge/deployment are outside the current experiment goal.
