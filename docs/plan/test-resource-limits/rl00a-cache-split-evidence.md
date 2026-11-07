# RL00a: owner-approved cache split and local evidence

Status on 2026-11-07: the amended local 26-pair matrix passed. Live CI for
this revision is not approved or executed; RL00a remains incomplete. Both
[earlier CI failures](rl00a-evidence.md) retain their original verdicts.

The owner selected A after reviewing
[the diagnostic failure and explicit oracle proposal](rl00a-diagnostic-evidence.md#owner-approved-next-step-separate-cache-verdicts).
The [updated protocol](rl00a-protocol.md#owner-approved-cache-split-after-the-diagnostic-ci-failure)
separates dirty-cache containment from successful file-cache reclaim. This is
the approved change to future experimental verdicts, not a product threshold
change or a reinterpretation of historical failures.

## Implemented distinction

The original `_cache` writer function remains byte-identical to diagnostic
revision `b951b1733d9898bca5d9981ee13ac38eaec2285f`. It writes 40 MiB under
the same 32 MiB leaf. The new `dirty-cache` case accepts native zero only
without own/ancestor OOM. A native SIGKILL requires increased leaf-local OOM
and kill counters and no ancestor-local OOM, and is reported as an
`own-memory-violation`. Unknown exits or mismatched evidence fail the proof.
A characterization pass means that a violation was correctly detected; it
does not make the payload compliant or convert OOM into successful reclaim.

The separate `cache-reclaim` action writes every byte of a new anonymous disk
file, flushes and fsyncs each 4 MiB, then retains its open descriptor across
two observation barriers. It rereads the whole file between them. The case
requires native zero, ten successful fsyncs, all 40 MiB written and read,
no OOM, positive pressure/reclaim counters and complete file evidence.

The child records file size, allocation, zero links and read-only `mincore`
residency. Both checkpoints must identify the same file. Missing pages of
that already-written, still-open nonsparse file establish actual file-cache
eviction. Charged-file observations and increased leaf-wide file-refault
counters during the controlled reread corroborate the observation. The
refault counter includes the entire leaf and its evidence files; it is not
an exact per-inode page count. No mapping writes, truncation or explicit
cache eviction create the result.

Cache helpers moved into `rl00a_cache.py` to meet existing structure limits.
The provider, guardian, cgroup primitives, driver and workflow remain
byte-identical to the diagnostic revision. All existing runtime, memory,
task and swap caps remain. New barriers and instrumentation consume the
original four-second payload budget and six-second absolute deadline;
the supervisor also requires observing the native exit before payload stop.
No fresh barrier grace period replaces that deadline.

## Complete local observation

One frozen set of eight captured input files ran all 13 cases on both host
and prepared paths, serially, on Linux 5.15.0-136-generic, x86_64 and Python
3.10.12. All 26 unique pairs passed, all 26 unrelated sentinel observations
proved survival, and all required invocation/service cleanup observations
completed. The [public summary](rl00a-cache-split-local-evidence.json)
retains each case's readbacks, native outcomes and cleanup evidence without
developer paths or process identities.

| Ordinary disk case | Host | Prepared |
| --- | --- | --- |
| Dirty writer native status / own OOM | 0 / 0 | 0 / 0 |
| Dirty writer complete case duration | 0.746 s | 0.703 s |
| Reclaim native status / own OOM | 0 / 0 | 0 / 0 |
| Reclaim complete case duration | 0.880 s | 0.751 s |
| Written target bytes absent from residency checkpoint | 17,350,656 | 17,350,656 |
| Leaf-wide file-refault delta during reread | 10,240 | 10,274 |

The successful reclaim cases recorded charged file pages and positive local
max/reclaim events while their file remained open. These observations support
successful reclaim without an own violation for this fixture and host. They
are not calibrated performance limits or a portable completion guarantee.

Kill-to-empty observations were approximately 0.059–5.91 ms, including
already-empty completions and excluding detection/reporting. Independent
systemd cleanup after guardian death completed in approximately 1.10 and
1.17 seconds, within the configured stop bound. Residual charged memory
before directory removal was sometimes nonzero. No immediate-zero release
or worst-case scheduling claim follows from successful directory removal.
`memory.peak` remains unavailable locally, so samples cannot prove zero overshoot.

The private raw summary has SHA-256
`f7f9b4befdaf41b1ad5006673af5455ef74199a8ebfffe0a0c6294406238cf86`.
The eight-input manifest has SHA-256
`e94be3c3314bfeafb0b14da641259a111de8d76f8e819c4baf4b8667b2acc114`.
All captured source copies match those frozen hashes and the unchanged input
bytes after the matrix. The captured Git HEAD is the preceding report commit
`06113a4825820d050d406b42c8c2ba9c8e3a11a2`; it does not identify the tested
worktree bytes. Binding to the review commit is by the eight retained source
copies and hashes, verified again before publication. No subset from another
revision substitutes for this complete matrix.

## Fault evidence and normal checks

A separate bounded tmpfs probe ran the original writer with the same cap.
It produced native SIGKILL, leaf-local `oom=1` and `oom_kill=1`, and the
`own-memory-violation` verdict. The guardian and sentinel survived; the
invocation was removed. Its owned RAM directory was removed after retaining
the evidence. This is fault injection, not a positive disk-reclaim case or
an explanation of either earlier CI failure.

Two healthy preliminary observations replayed against the frozen classifier
retained their expected verdicts. Fourteen controlled corruptions covering
missing observations, absent file eviction/refault, incomplete writes/fsyncs,
sparse/changed files, own/ancestor attribution and unexpected exits were all
rejected. An expired absolute barrier deadline was also rejected even when
the barrier already existed: 15 negative checks, zero false passes in this
finite set. Replay exercises validation logic; actual kernel evidence comes
from the separate live runs above.

Pinned Ruff, strict Pyright and the project's actual structure analyzer
passed for all retained RL00a sources under the existing policy. The ordinary
managed quality hook remains required before offering the concrete revision
for CI approval. No production policy, hook or threshold bypass is added.

## Next required observation

Review the concrete revision and all eight input hashes, then obtain separate
approval for live publication under
[the verification gate](verification.md#sequential-feasibility-and-integration).
The workflow is unchanged, with Git blob
`9d9e5221c1f16f2d284d7ea0c28cc317f40cf59d` and SHA-256
`0018b43c164f5d12df956128a23e7b460a4915527b70d44a52a5a1a7bdadc8ce`.
The new live observation must retain all eight source copies and all 26 pairs;
neither a green job alone nor local success completes RL00a.

Framework attribution, selective checks, calibration, product integration and
export adoption remain later RL00/RL01–RL06 work. This experiment does not
claim arbitrary containers, aarch64, nonzero time namespaces or hostile
same-UID isolation.
