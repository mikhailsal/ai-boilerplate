# RL00b/c: recommendation

Recommendation on 2026-11-09: do not integrate per-test resource limits into
`quality`, hooks or exported projects on this evidence. RL01 to RL06 stay
unauthorized, and nothing here approves a merge or deployment. The decisive
reason is measured: the protected arm exceeded the owner-approved overhead
criterion A in every environment of the only complete required timing cell.
Gaps in attribution, cleanup and unperformed required work add to it. The
[evidence page](rl00bc-evidence.md) holds the results, and the
[receipts record](rl00bc-receipts.json) binds them to CI artifacts.

## Reason

Criterion A allows a protected p95 wall time of at most twice the native p95
plus two seconds, including fallback. For the small browser corpus the protected
p95 was 18.2 to 22.2 seconds against limits of 9.1 to 10.9, about five times
native on x86_64 and aarch64, in host and prepared modes. Even the fastest
protected sample exceeded the limit. The instrumented canonical trial matched
the native run, and the cost is the eight fresh probes that follow, each about
half of a whole native run, not memory or controller work. First adoption and
unknown influence expand to the full corpus, so this fallback arm applies to
every first run and cannot be waived without a recorded amendment.

The result is specific. It measures the full fresh-probe fallback of one small
browser corpus. It does not prove that a cheaper protected arm is impossible,
but no evidence supports one: narrow selection cost was not measured and
shared-worker attribution is recorded as unsupported.

## Requirement-by-requirement status

| Requirement | Evidence | Status |
| --- | --- | --- |
| Raw-source and artifact binding | 53 artifacts with verified SHA-256 and the frozen commit | Met, except 15 lost Dart artifacts |
| Method and support matrix | Browser: three arms observed in four environments | Browser only; Dart lost, others unrun |
| Verdicts and canonical parity | Browser compatibility passed; `child` correctness unproved; coverage and scenario reconciliation pending | Unproved |
| Parity and selection proofs | Finite Python fixture: 19 candidate steps and selection pressure | Observed for that fixture only |
| Measurements and distributions | Browser small corpus, twenty pairs per cell | Criterion A failed; other sizes and profiles unrun |
| Lifecycle, races and faults | Admission, both races and drift observed; no cleanup after requester SIGKILL | Partial; pending proofs remain |
| Adoption | Python overlay chains: three complete, one `update-check` failure | Partial; no real hook or export enforcement |
| Limitations | Listed in the evidence page | Recorded |

## Classification of outcomes

Proven failures with retained native evidence are criterion A exceeded in all
four browser cells, no observed automatic cleanup after requester SIGKILL in all
four Python cells, and one adoption `update-check` failure without a resource
violation, whose cause is unattributed.

Unsupported or unproved attribution covers the browser `child` identity and
phase scope in all four cells, with `slow`, `retained` and `justified-allowance`
also unproved, shared-worker attribution, and every Dart verdict.

Setup failures are the upload rejection that lost 15 Dart artifacts, the
verdict-mapping defect that turned complete lifecycle, nested and adoption
records red, and one Dart bootstrap failure with an unattributed cause. The
first two are fixed in commit `796a12c` but have not run live.

Unperformed work is 48 Node, PHP and Python correctness, compatibility, methods
and measure cells; the `large` size; selection-cost, startup, guardian and total
invocation measurements; shared-worker instrumentation; adoption beyond the
Python overlay, including human understanding, administrator wait and missing
delegation; abrupt guardian and controller death recovery; and the other
pending proofs listed per phase.

## Next decision for the owner

The evidence supports closing RL00 as a no-go for the measured design. Any
continuation needs a new frozen commit, a new gate and a new explicit approval
before a live run; this one does not authorize reruns.

1. Close RL00 here. This is recommended: completing the matrix cannot change the
   measured browser result, and the cost of the remaining runs buys documentation,
   not a different decision.
2. Complete the matrix with the fixed harness. It would fill the Dart and
   other-profile gaps and rerun the red phases, at the price of a new approval
   and about thirteen more runs.
3. Evaluate a different protected design under a separately identified
   protocol, for example per-case limits inside the canonical run or an
   explicitly approved narrower scope of invocation containment only. Changing
   criterion A after seeing this result needs a recorded amendment and cannot
   relabel it, and the plan forbids a silent suite-only fallback.

Before any further live run, attribute the requester-SIGKILL cleanup gap, the
`child` oracle result and the adoption `update-check` failure.
