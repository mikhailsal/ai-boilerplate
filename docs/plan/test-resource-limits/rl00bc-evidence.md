# RL00b/c: live campaign evidence

Status on 2026-11-09: the owner-approved live campaign ran on frozen commit
`9acec68e0a8196276cadbf1200b1e5d56928115d` and stopped under the owner's stop
rule after every complete browser timing cell exceeded the approved overhead
criterion. RL00b and RL00c are therefore partial. Unrun, lost and pending work
is listed explicitly, the [recommendation](rl00bc-recommendation.md) draws the
conclusion and the [review](rl00bc-review.md) records the outside audit. No
merge, deployment or integration into `quality` or exported projects happened
or is claimed.

## Approvals, bounds and receipts

The owner answered `A` to decision D1 in the [protocol](rl00bc-protocol.md),
then approved the frozen commit, both workflows, their finite bounds, the order
below and the stop rule. Only D1 is recorded in a committed page; the other
answers were given in the working session, and each measurement record marks its
criterion approval as caller-asserted pending an independent approval audit. The
13 trigger refs were created at that commit through the GitHub REST API, so no
Git push or hook was involved. Nothing was rerun until green. The order was
prepare; correctness, compatibility and methods; lifecycle, nested, faults,
selection pressure, both guardian races and candidates; measure; adoption.

The stop rule ends the campaign when a prepare job fails, a job leaves an
uncleaned or uncontained subtree, or a complete required measurement cell
exceeds criterion A; the last case still allows the adoption run. Observed
comparison failures do not stop it, but Node, PHP and Python jobs of a phase
start only after its Dart and browser jobs succeed.

Rule (a) was not triggered: four of four prepare jobs succeeded. Rule (b) was
not triggered in the 53 retained artifacts: no outer or guardian cleanup error
was recorded, every unrelated sentinel survived, every service root was observed
removed and no guardian error was recorded. The outer cleanup list holds raised
exceptions, not the exit status of each shutdown command, so the independent
sentinel and root observations carry this finding. Expected refusals in the
lifecycle and nested records carry their own cleanup note (`leaf was not
created`), and the race records note that the guardian owns cleanup after
closing; both belong to the tested behavior. The 15 lost Dart artifacts cannot
be checked. Rule (c) was triggered by the measurement below.

The [receipts record](rl00bc-receipts.json) lists the 13 runs, all 68 matrix
jobs with their conclusions, the 53 retained artifacts with identifiers, sizes
and ZIP SHA-256 values, and the job logs that show why 15 Dart artifacts were
lost. Each hash was recomputed from the downloaded ZIP and equals the digest
GitHub reports; each artifact's identity file names the frozen commit. Artifacts
expire after one day, so the hashes are the retained binding and the raw
archives are not committed; the [timing samples](rl00bc-measurements.json)
behind the decisive result are, so the timing section can be recomputed from the
repository. After the freeze only the status paragraphs of the protocol and
proof pages changed. Commits and pushes in this task skipped local hooks under
the owner's scoped permission; CI ran every heavy check.

## Results by phase

| Phase | Run | Cells | Recorded result |
| --- | --- | --- | --- |
| Prepare | [42554150955](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42554150955) | Python 4 | Prepared in all four |
| Correctness | [42554757095](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42554757095) | Browser 4, Dart 4 lost | Browser `comparisons-failed`, see below |
| Compatibility | [42554758633](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42554758633) | Browser 4, Dart 4 lost | Browser `pass`, no errors or gaps |
| Methods | [42554757751](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42554757751) | Browser 4, Dart 1 kept, 3 lost | Browser `observed-with-required-proofs-pending` |
| Lifecycle | [42556021184](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42556021184) | Python 4 | `observed-partial`, nine cases |
| Nested | [42556022163](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42556022163) | Python 4 | `observed-partial`, six cases |
| Faults | [42556023230](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42556023230) | Python 4 | `nonpass`, requester SIGKILL |
| Selection pressure | [42556025730](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42556025730) | Python 4 | Success on the finite fixture |
| Race, launch first | [42556026757](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42556026757) | Python 4 | Guardian killed the launched payload |
| Race, closing first | [42556028502](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42556028502) | Python 4 | Payload never launched |
| Candidates | [42556030142](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42556030142) | Python 4 | Success, 19 steps |
| Measure | [42558123675](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42558123675) | Browser 4, Dart 4 lost | `no-go`, see below |
| Adoption | [42561375476](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42561375476) | Python 4 | Full chain in 3, one stopped |

Node, PHP and Python correctness, compatibility, methods and measure jobs were
never started: 48 cells, skipped because the Dart and browser jobs of those
phases failed. Lifecycle, nested and the three adoption chains that finished
show red jobs only through the verdict-mapping defect described below.

In all four browser correctness cells the single recorded mismatch is the
oracle's own text, "child selected identity or phase scope unproved". Native,
setup, teardown, parameter-heavy and justified targets show own-memory
attribution after entry in the finite fixture. The `child`, `slow`, `retained`
and `justified-allowance` targets stay `unproved`. For `child` the identity
binding is recorded as bound in the canonical and strict runs, so what is
missing is a valid phase attribution: in the strict run the allocation did not
complete, no allocation-end event exists, a later phase was observed and the
kernel boundary came from a later snapshot. OOM counters grew after entry, but
that growth cannot be placed inside the allocation phase. The worker oracle
observed overlap and claims no case-memory attribution. Seven required proofs
remain pending, among them real Git candidate mutations, canonical coverage and
scenario reconciliation, order perturbation and owned-child membership.

Browser methods observed all nine label-by-arm combinations (ordinary,
excessive and justified against full fresh, selected and shared-worker arms).
The selection was the first-adoption full fallback, and shared-worker
attribution is recorded as unsupported because lifetime evidence is not case
certification. Eight required proofs remain pending, including narrow selection
and its cost.

Lifecycle and nested check their expected outcomes internally and reach
`observed-partial` only when every check passed and no cleanup error or overrun
was recorded. Lifecycle recorded serialized admission of independent and
concurrent callers, refusal of above-capacity requests with no native payload,
cooperative cancel, recovery, a deadline-clamped timeout and rejection of an
expired entry. Its scope is sibling admission, not a real guardian race. Nested
recorded concurrent, over-memory, over-tasks, cancel, recovery and deadline
cases of a fixed fixture, not a general scheduler. Both list further pending
proofs.

In every faults cell the requester stopped about ten milliseconds after its
SIGKILL, but neither a stop of its native child nor removal of the original leaf
was observed within the three-second window, so automatic cleanup was not
observed. Manual cleanup afterwards is recorded separately and never counted.
Limit drift and membership drift behaved as expected. The mechanism behind the
missing cleanup is not attributed. Both race phases succeeded: with launch first
the guardian killed the launched payload (native status -9), and with closing
first the published marker prevented any launch. Candidates and selection
pressure succeeded only for their finite fixtures and claim no selection
soundness.

All 16 Dart jobs failed. Fifteen retained no artifact because the artifact
service rejected the whole upload over a colon in a Dart event file name; each
job log, listed in the receipts, shows that rejection and the same generic
collector error, so their verdicts are unobservable. The sixteenth, methods on
the x86_64 host, failed in dependency bootstrap with native exit 3 and no
resource violation. Its retained output ends inside a truncated download
listing, so the cause is unattributed and may be transient.

## RL00c timing: criterion A

Each of the four browser cells ran twenty interleaved pairs of the small corpus,
eight native identities from four examples and two projects, ten pairs in each
order. The native arm is one canonical run. The protected arm is the
instrumented canonical run plus one fresh strict probe per case, nine trials.
The `large` size ran in no cell because the first complete cell was a no-go.
Times are wall seconds; p95 is the second largest of twenty and was recomputed
from the raw samples.

| Environment | Native p50 / p95 | Protected p50 / p95 | Limit | Ratio of p95 |
| --- | --- | --- | --- | --- |
| x86_64 host | 3.445 / 3.534 | 17.922 / 18.183 | 9.069 | 5.14 |
| aarch64 host | 3.671 / 3.791 | 18.774 / 19.396 | 9.581 | 5.12 |
| x86_64 prepared | 4.243 / 4.431 | 22.041 / 22.173 | 10.861 | 5.00 |
| aarch64 prepared | 3.694 / 3.865 | 18.767 / 19.177 | 9.731 | 4.96 |

The limit is twice native p95 plus two seconds. Even the fastest protected
sample (17.776, 18.563, 21.806 and 18.383 seconds) exceeds it, so no outlier
decides the result. The per-trial records separate the cost. The instrumented
canonical trial took about the same median time as the native run, within 0.03
seconds in every cell, while the eight fresh strict probes took a pooled median
of 1.80 to 2.21 seconds each, about half of a whole native run, and their sums
add a median 14.4 to 17.8 seconds per sample. The protected arm's median
controller CPU was 0.29–0.43 seconds against 0.06–0.08 in the native arm, and
median leaf memory peaks were 475–482 MiB in both arms (largest protected peak
485 MiB, largest native 514 MiB). The cost is therefore repeated fresh probes,
not instrumentation, memory or controller work. Playwright traces of the timing
cells were not uploaded, in the frozen and the fixed packaging alike; the
correctness and methods artifacts keep theirs.

The measurement excludes provider and bootstrap setup, guardian CPU and total
invocation memory. Its wall times include runtime startup, fixture
materialization and parsing, but not as separate costs. Narrow selective
checking, shared-worker timing, selection cost, verdict usefulness and every
other profile were not measured. A timing result cannot certify that unmeasured
work.

## Adoption chains

| Environment | To first protected own test | All recorded phases | Outcome |
| --- | --- | --- | --- |
| x86_64 host | 137.9 s | 490.6 s | Chain complete |
| aarch64 host | 94.2 s | 357.5 s | Chain complete |
| x86_64 prepared | 136.4 s | 370.7 s | `update-check` failed |
| aarch64 prepared | 119.7 s | 390.9 s | Chain complete |

The sums add recorded phase durations and exclude administrator wait, human
understanding and novice usability, which are unmeasured. The fixture is Python
only and the protection is an experimental standalone overlay: unmodified
exports and hooks enforce no resource policy. Missing delegation was not run,
and the update fixture changes an exported document, not a matched
resource-policy core. In the failed cell the exported project's own check
reported one failing end-to-end test of the quality core (native exit 1, no
resource violation, peak 1,137 MiB under the 3,072 MiB cap). The same phase
passed in the other three cells, nothing was rerun, and the cause is
unattributed.

## Harness defects found

The earlier static review found neither defect; the campaign exposed both.
First, the upload step failed on colon-bearing Dart file names and discarded
whole artifacts. Second, the driver accepted only a true `success` flag, which
the lifecycle, nested and faults collections never set, and tested the adoption
result as a list although it is a mapping with a deliberately unrun entry, so
those jobs were red although their records are complete.

Commit `796a12c` fixes both: records are packed in a tar archive with a verdict
summary in the job log, the three partial collections pass at `observed-partial`,
and adoption passes when its final phase is present. The [review](rl00bc-review.md)
found that adoption rule too weak, and the commit that records the review
tightens it: the final phase must itself have succeeded and only the delegation
proof may stay unrun. New unit tests pin the mapping; none ran locally, so CI is
their first execution. The fixed workflow has not run live, so the lost Dart
cells and the red jobs above stand as recorded. Any continuation needs a new
frozen commit and a new owner approval.
