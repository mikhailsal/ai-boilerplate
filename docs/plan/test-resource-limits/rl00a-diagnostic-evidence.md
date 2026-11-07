# RL00a: diagnostic revision evidence

Status on 2026-11-07: diagnostics are verified; the required CI proof failed
again. This report supplements [the local and first CI evidence](rl00a-evidence.md).
The [preregistered protocol](rl00a-protocol.md) remains unchanged. No fixture
amendment below has been approved or implemented.

## Local verification of the diagnostic amendment

The seven diagnostic inputs passed one complete local matrix on Linux
5.15.0-136-generic and Python 3.10.12. All 24 unique host/prepared pairs passed,
and all 24 sentinel records proved survival. The two cache cases recorded
native wait/poll status zero, an exited child, empty missing-diagnostic lists,
ext4 backing and keyed before/after memory statistics. Their complete case
durations were approximately 0.86 and 0.75 seconds, with positive max events
and no OOM. These are single-run observations, not calibrated performance bars.

The private raw summary has SHA-256
`156da6241b7c2d77609271d3ec862203c85e8baa99718f781cae07d832b97563`;
the seven-input manifest has SHA-256
`7425a667f22f1d938587d44cfe046a8bf5e8a4550b33fe8b8c2ceb542614622a`.
The run captured uncommitted source bytes over the prior report revision;
all seven copies were subsequently verified against committed
`b951b1733d9898bca5d9981ee13ac38eaec2285f`. The captured Git HEAD alone
does not establish that binding.

A separate controlled fault probe placed the same cache writer on tmpfs under
the same finite memory/task/time limits. It deliberately failed the original
required-success assertion: native wait/poll status was SIGKILL, leaf-local
`oom=1` and `oom_kill=1`, the sentinel survived and the invocation was removed.
This verifies failed-case evidence retention. It is not an ordinary disk-case
pass, is not counted in the 24-pair matrix, and does not identify either real
CI filesystem or writeback cause. Its temporary RAM directory was removed.

Controlled mechanism checks verified primary-exception preservation when
observation or service cleanup fails, and failure after a healthy run whose
cleanup or sentinel observation fails. Ruff, strict Pyright and structure
checks passed. Managed pre-commit and pre-push checks passed with all six
component coverage floors satisfied. The diagnostic workflow has Git blob
`9d9e5221c1f16f2d284d7ea0c28cc317f40cf59d` and SHA-256
`0018b43c164f5d12df956128a23e7b460a4915527b70d44a52a5a1a7bdadc8ce`.
Its only workflow change retains hidden report paths; permissions, execution
commands and watchdogs are preserved.

## Second real CI observation

The owner approved publishing that exact revision and running its bounded
workflow. [Run 42327373724, attempt 1](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42327373724)
tested `b951b1733d9898bca5d9981ee13ac38eaec2285f` and concluded with failure.
Its [artifact](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42327373724/artifacts/13555248833)
has verified ZIP SHA-256
`a40d6e2555686b1ac9c7b5cf38c1038282133eee699c48b83e3b67b4ae9b8418`.
All seven captured source files match the commit and identity hashes, including
`source/.github/workflows/resource-proof.yml`. The environment remains x86_64,
Linux 7.0.0-1017-azure and Python 3.12.3 on the Ubuntu 24.04 runner image.

[The second CI summary](rl00a-diagnostic-ci-evidence.json) records six passed
host pairs: placement, partial setup, own memory, ancestor memory, nested
budgets and caught task denial. Their sentinels survived; invocations were
emptied and removed before the original deadline. The seventh pair,
`host/cache-reclaim`, failed; the other 17 pairs did not execute.

| Failed cache observation | Retained value |
| --- | --- |
| Native wait / poll status | Both `-9` (SIGKILL); child exited |
| Leaf memory / swap readback | 33,554,432 / 0 bytes |
| Leaf-local events | `max=195`, `oom=3`, `oom_kill=1` |
| Last payload phase | `writing`, before explicit `fsync` |
| Backing mount | ext4 `/dev/root`, `data=writeback` |
| Sampled / kernel peak | 33,550,336 / 33,558,528 bytes |
| Invocation / control local OOM | Both zero |
| Guardian / sentinel | Both survived |
| Guardian cleanup | Invocation empty and removed, 5.717 seconds before deadline |
| Missing cache diagnostics | Empty list |

The kernel peak exceeds the read-back leaf maximum by 4,096 bytes; sampling
missed that transient overshoot. The kernel explicitly permits temporary
overshoot of [memory.max](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory-interface-files).
This is consistent with the approved kernel-semantic contract, not evidence
for an exact physical-memory ceiling.

Matching native SIGKILL and leaf-local OOM establish a leaf-limit violation.
The original required-success cache assertion therefore correctly fails.
The complete 40 MiB write, successful reclaim and peak memory composition
remain unproved. Post-death `memory.stat` has already lost most file/anonymous
pages; it cannot establish why reclaim failed. The ext4 mount alone cannot
establish a filesystem defect or explain the first run. The kernel documents
[filesystem-dependent writeback](https://docs.kernel.org/admin-guide/cgroup-v2.html#writeback),
without promising that every dirty-file workload completes under a small cap.

Guardian cleanup took approximately 0.038 ms on an already-empty subtree,
excluding detection/reporting. It retained 1,314,816 charged bytes before
directory removal. The failed driver never reached its service-empty success
assertion or wrote `result.json`; guardian invocation removal is the observed
cleanup evidence. Neither immediate zero residual charge nor complete service
cleanup certification is inferred from it. Both real failures remain retained.

## Proposed next decision: separate cache verdicts

This is a material fixture/oracle proposal for owner review, not an implemented
fix. The evidence rejects treating the current writer as a portable proof of
successful reclaim; it does not identify a kernel regression. Kernel containment
does not require every workload to finish successfully. The plan still requires
positive evidence that successful reclaim is not reported as a violation.

The recommended amendment would retain the original writer unchanged as an
additional required dirty-cache characterization, and introduce a separate
required reclaim fixture. This explicitly relaxes the original dirty-writer
success gate for future matrices: a proven own OOM may satisfy containment
characterization while still being reported as a resource violation. Only the
separate reclaim fixture would require native success without OOM. The
proposed contract is:

1. Keep the original dirty writer, file size, cap and all historical nonpasses.
   A future native zero without own OOM is native success. Proven own OOM is
   reported as a resource violation, never as successful reclaim. Each observed
   outcome still requires supervisor/sentinel survival and owned cleanup;
   missing evidence, unexpected exits and deadline exhaustion are nonpasses.
2. Add a 40 MiB anonymous disk-file fixture under the same 32 MiB leaf that
   flushes and fsyncs every 4 MiB. Verify completed writeback and charge evidence;
   this is a proposed workload, not a guarantee of portable completion. Require
   native zero, no local OOM and positive max/reclaim counters within the original
   deadline. Counters alone are insufficient: correlate all 40 MiB of new,
   nonsparse first writes inside the fresh leaf with file size/allocation and
   held-open file/dirty/writeback charge snapshots before descriptor closure.
   No other writer, truncation or explicit cache eviction may explain missing
   resident file pages. Missing file-reclaim evidence remains a nonpass;
   generic `pgsteal` alone cannot establish which pages were reclaimed.
3. Run all 13 cases on both paths in a fresh 26-pair matrix from one frozen
   revision. Preserve six-second deadlines, cleanup reserve, hierarchy, swap
   and task caps. New fixture setup consumes the existing deadline. A timeout
   or OOM in the required-success fixture remains a failure.
4. Review the concrete patch and local matrix before separately approving a
   new live revision under [the verification gate](verification.md#sequential-feasibility-and-integration).
   Existing 24-pair attempts remain historical failures under their original
   oracle; they cannot be relabeled as the amended 26-pair proof.

This changes the experiment's coverage and expected outcomes; it needs explicit
review rather than an automatic retry. Keeping the existing oracle instead
requires further bounded investigation of the original write path. Neither
option authorizes product integration or an RL00 go decision today.
