# RL00b/c: outside review and audit

Status on 2026-11-09: after the campaign, two read-only reviews examined commit
`9448736`: one of the harness sources and workflows, one factual audit of the
[evidence](rl00bc-evidence.md) and [recommendation](rl00bc-recommendation.md)
pages against the retained raw artifacts. Neither found a defect that overturns
the criterion A result. Both found issues in the wording or in the harness, and
each has a recorded disposition below.

## Scope and limits

The reviews ran with the OpenAI Codex command-line tool 0.167.0, model
`gpt-6.1-sol`, in a read-only sandbox with instructions not to run tests,
linters, the harness or any network access. The reviewers use a different model
vendor than the author, which lowers shared bias, but this is not a fully
independent audit: the author wrote the prompts, held the raw data and triaged
the findings, and no subagents were used.

The audit recomputed all four timing cells from the raw samples, found every
timing trial's native exit zero with complete cleanup, matched all 53 identity
files and 87 recorded source hashes to the frozen commit, and counted sentinel
survival and service-root removal at 53 of 53. The source review found nothing
in pairing, timer boundaries, nearest-rank p95, the criterion arithmetic,
interrupted cells, the stop rule, job gating, permissions, secret handling or
source identity.

Not checkable by them: the owner's approvals and the hook exception, which were
given in the working session; the REST creation of the refs; the absence of
unlisted reruns; where every historical heavy check ran; ZIP integrity and the
authenticity of GitHub's metadata. The job logs behind the lost Dart artifacts
were not available to them, so the author added their key lines to the receipts.

## Source review findings

| ID | Finding | Disposition |
| --- | --- | --- |
| R1 | Artifacts expire after one day and hashes alone cannot recreate samples | Partly addressed: the timing samples of the decisive cells are committed; other raw records stay bound by hash only |
| R2 | Playwright traces of the timing cells were never uploaded | Recorded in the evidence; unchanged, and a continuation must decide |
| R3 | An empty outer cleanup list does not prove each shutdown succeeded | Recorded in the evidence; sentinel survival and root removal carry the finding |
| R4 | The adoption verdict could pass with an unrun or missing final phase | Fixed with unit tests in the commit that records this review; CI is their first run |
| R5 | A push to a phase ref reruns it on the old approval, with no approved-commit check | Not fixed; the 13 trigger refs still exist |

## Documentation audit findings

The audit raised eight discrepancies and all were corrected in the commit that
records this review. The recommendation had listed shared-worker instrumentation
as unperformed although the methods phase ran it, so only its timing is
unperformed. It had also promised a completed matrix from the collection fixes
and about thirteen runs, but the phase gate would again skip every Node, PHP and
Python cell after the known browser failures. The `child` target has a bound
identity; its phase attribution is what stays unproved, and OOM growth cannot be
placed inside the allocation phase. Further corrections are the canonical
median difference (up to 0.027 seconds, not 0.02), the statistics for probe
sums, controller CPU and leaf memory, the scope of the cleanup statements, the
startup and collection costs that wall time includes without separating them,
and the Dart row of the support table.

## Open before any further live run

The three unattributed results named in the recommendation, the trace decision
(R2), recorded shutdown statuses (R3), and an approved-commit and runner check
with renewed authorization after a stop (R5). The owner's independent audit of
the approval record is also open.
