# RL00a: local evidence and first CI nonpass

Status on 2026-11-07: the final local 24-pair matrix passed; the first real CI
run stopped after six passes and one required-proof failure. RL00a is incomplete.
The active owner goal authorized the bounded experiment described in the
[protocol](rl00a-protocol.md). This is not a successful RL00 release decision
and does not integrate limits into `quality` or exported projects.

## Observed local behavior

The developer host uses Linux 5.15.0-136-generic, x86_64, systemd 249.11 and
unprivileged Python 3.10. The delegated unit exposes `memory`, `pids`,
`memory.events.local` and `cgroup.kill`; `memory.peak` is absent. The prepared
path receives an already-limited writable branch from a separate provider.
Both paths use the same descriptor-owned runner and external guardian contract.
No persistent machine configuration or sudo was used locally.

[The public evidence summary](rl00a-local-evidence.json) records all 24 final
observations, configured limits, event counters, native outcomes, cleanup and
source hashes. The preceding 22 successful observations and four nonpasses
remain in the private raw record, whose checksum is published in the summary.
Absolute developer paths and process identities are omitted from Git history.
The raw final run retains source bytes and original identity/deadline evidence.
It ran after the concurrent native quality check had finished. One run does
not establish performance stability.

| Required observation | Developer host | Prepared branch |
| --- | --- | --- |
| Pre-exec placement, finite ancestor caps, unprivileged identity | Observed | Observed |
| Oversized setup and partially missing controller start no payload | Observed | Observed |
| Own 32 MiB leaf kills an 80 MiB allocator with local OOM evidence | Observed | Observed |
| Parent 96 MiB exhausts while both 64 MiB leaves have no own max event | Observed | Observed |
| Two nested branches retain 96/64/32 MiB and 16/8/4 task caps | Observed | Observed |
| Live parent remains charged; above-ancestor request fails promptly | Observed | Observed |
| Caught task EAGAIN still appears as a violation with native exit zero | Observed | Observed |
| Original 40 MiB disk-cache workload completes under 32 MiB without OOM | Observed | Observed |
| SIGINT, inherited deadline and supervisor SIGKILL remove detached children | Observed | Observed |
| Control-leaf OOM kills supervisor; independent guardian survives | Observed | Observed |
| Guardian SIGKILL activates independent systemd subtree cleanup | Observed | Observed |
| Unrelated sentinel retains the same live pidfd throughout | Observed | Observed |

The control-pressure repetitions recorded control-local `oom=1` and
`oom_kill=1`, native SIGKILL before the guardian deadline, and no invocation-local
OOM. This distinguishes a supervisor OOM from the guardian imposing a timeout.
In the ancestor experiment, local parent OOM and victim-leaf `oom_kill` counters
identified the limiting parent separately from its victim; the victim was not
reported as an intrinsically expensive case.

In the final matrix, cgroup-kill-to-empty observations were approximately
0.06–6.29 ms; this includes already-empty normal completions and excludes
detection and reporting. All recorded
finishes preceded the original six-second deadline. After guardian death,
systemd cleanup was observed in 1.21–1.24 seconds, within its configured stop
bound. These are observations on this host, not worst-case kernel scheduling
guarantees. No uninterruptible leftover was observed.

Own-leaf memory samples reached the configured ceiling without observed
overshoot. Sampling is a lower bound on peak usage; it does not establish zero
overshoot. Exact local peaks remain unavailable on this kernel. Kernel hard-limit
semantics, including possible transient overshoot, remain the owner-approved
contract from the plan.

## Nonpasses retained rather than retried into a clean result

One earlier 80 MiB / 64 MiB disk-cache trial completed successfully with
positive `memory.events.local:max` and no OOM. It demonstrates successful
reclaim without an own memory violation for that older fixture only.
The first full run incorrectly used an extra two-second sampler timeout;
the payload completed in 2.16 seconds. The sampler was corrected to consume
the original four-second payload deadline, and a targeted cache/timeout run
proved both completion and independent deadline enforcement.

Subsequent full runs hit actual disk writeback/read latency at the original
cutoff. Halving file size and cap did not establish a stable final fixture.
The final cache nonpass has zero OOM counters, reason `deadline`, successful
subtree removal and about 28 ms kill-to-empty latency. It must not be labeled
as a memory violation or as a successful full run. A separate ancestor-memory
trial also reached its deadline after recording ancestor OOM; three prior host
trials and the prepared-path trial completed. Neither failure is discarded.

After the final source changes and completion of the native checks, the full
matrix passed without increasing any limit. The original dirty-file cache
fixture completed in 0.36 and 0.40 seconds on the host and prepared paths;
both had `max=306`, zero OOM counters and native exit zero. This demonstrates
successful execution under charged-memory pressure. The max counter alone is
not direct telemetry of which file pages were reclaimed, and no per-page
attribution or contention-independent timing guarantee is claimed.

One interrupted old cache writer left a named temporary file. Its size and
explicit owner cleanup remain in the private raw record. The current writer uses an anonymous
disk file whose descriptor closure also cleans it after SIGKILL; the later
timeout left no named cache file. Session limits were not increased. This
failure is relevant to the later residual-charge and workload-cost gates.

## Approved CI experiment

[resource-proof.yml](../../../.github/workflows/resource-proof.yml) runs only
when the dedicated `spike/rl00a-proof` branch is pushed. It checks out the exact
revision, runs the complete 24-pair matrix on Ubuntu 24.04 and uploads source
identity plus evidence, even on failure. It has read-only repository permission,
no application secrets, a six-minute job limit and a four-minute outer command
watchdog. Existing required quality jobs are unchanged.

The CI system manager needs sudo to create UUID-named transient delegated
services. Each service sets `User`/`Group` to the ordinary runner identity,
the same finite caps and manager-side cleanup. The supervisor and payload stay
unprivileged; the outer provider uses sudo for only those units' creation,
inspection and stop operations. Units expire independently of the outer driver. There is no persistent
sysctl, host service installation or production deployment. Template export
excludes this maintainer-only workflow together with the acceptance helpers.

The owner approved publication and the real run on 2026-11-07, following
[the verification plan](verification.md). The public snapshot keeps the seven
locally proved source inputs unchanged while replacing raw developer diagnostics
with a sanitized summary. The original local commit stays unpublished and is
not an ancestor of the public branch. The workflow has Git blob SHA
`3ad0087f77621beecaa78f58d12cef47c1aac471`; the tested CI commit is
`e91777714a4e5d9097f8d66f7196db9990bb7d2e`.

## First real CI observation: required proof failed

[Run 42308432766, attempt 1](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42308432766)
started at 2026-11-06 22:56:54 UTC and concluded with failure. It ran on the
Ubuntu 24.04 image, Linux 7.0.0-1017-azure, x86_64 and Python 3.12.3.
[The public CI summary](rl00a-ci-evidence.json) records the observations and
their limits. The
[raw artifact](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42308432766/artifacts/13546957605)
has verified ZIP SHA-256
`9d5bfd25f9f19abf6e4c105748677f922e758372d06201a926308b6d5f89ff60`.

Six host pairs passed: placement, partial setup, own memory, ancestor memory,
nested budgets and caught task denial. Their sentinel checks passed, and each
invocation was emptied and removed before its original deadline. The own-memory
case recorded native SIGKILL and leaf-local OOM under its configured ceiling.
The ancestor case recorded parent-local OOM and two killed child payloads,
without either child hitting its own maximum. These are separate limiting
boundary and victim observations, not an attribution of expensive cases.

The seventh pair, `host/cache-reclaim`, failed before producing a case result.
Its last payload marker is `writing`, before the explicit `fsync` marker.
The invocation's hierarchical counters recorded `max=160`, `oom=2` and
`oom_kill=1`; invocation-local and control-local OOM counters remained zero.
The guardian survived, emptied and removed the invocation subtree, with
approximately 5.75 seconds remaining before the original deadline. The
recorded kill-to-empty call took about 0.034 ms on an already-empty subtree;
this excludes detection and reporting and is not a scheduling guarantee.
Residual charged memory before directory removal was 2,265,088 bytes, so this
does not prove immediate deallocation of all charged pages.

Payload-subtree OOM activity is established. The failed case did not preserve
its payload wait status, leaf-local counters or post-case sentinel observation.
It therefore does not establish the exact cause of the nonzero payload status,
the limiting leaf, sentinel survival for that failure, completed file bytes,
or the filesystem/writeback mechanism. Dirty-cache pressure is a hypothesis,
not a proven kernel regression or a successful reclaim observation.
The kernel documents distinct hierarchical/local counters and
[filesystem-dependent writeback](https://docs.kernel.org/admin-guide/cgroup-v2.html#writeback);
the artifact lacks the telemetry to distinguish those paths here.

Seventeen pairs were not executed: all prepared-path cases and the five host
death/interrupt/timeout cases. There is no full CI matrix or RL00a completion.
No run was retried and no budget or fixture was changed.

The identity file's seven hashes match the public commit. Six source copies
are present and hash-verified in the artifact. The workflow copy below
`source/.github` is absent because artifact upload excludes hidden paths by
default. Its hash was verified against the exact public Git blob, which does
not repair the missing captured copy.

## Concrete next observation proposal

Review a diagnostic-only amendment before another live experiment:

1. Keep the dirty 40 MiB file, 32 MiB leaf, original absolute deadlines,
   hierarchy, task caps and assertion that this required case must complete.
   Retain this failed run. Do not substitute a sparse or clean-cache workload.
2. In `rl00a_cases.py`, persist the cache payload's native wait status and
   before/after leaf snapshots before asserting success. Include keyed
   `memory.stat` observations and the filesystem backing the artifact directory;
   preserve evidence on exceptional paths as well.
3. In `rl00a_driver.py`, record sentinel pidfd liveness on failure before the
   driver's finalizer stops it. Preserve the original failure if diagnostic
   capture also fails. Missing diagnostics must remain explicit.
4. In `resource-proof.yml`, retain the captured workflow under `source/.github`
   by explicitly including hidden artifact paths, after reviewing the report
   directory for secrets. Permissions and resource watchdogs stay unchanged.
5. Review the concrete diff, new source/workflow hashes and bounded local
   verification before authorizing a further live diagnostic run. A diagnostic
   result is not a replacement for a later complete unchanged-source matrix.

This proposal changes no implementation yet. It first establishes attribution;
it does not presume that raising a ceiling, changing the workload or accepting
an OOM as successful reclaim is justified. A subsequent fixture or contract
change requires its own evidence and review. The
[preregistered protocol](rl00a-protocol.md#preregistered-verdicts) stops on a
required nonpass; this result remains no-go for RL00a completion.

## Limits and next evidence

Before a go decision, resolve the failed required CI proof and evidence gaps,
inspect every expected pair, and record an owner-reviewed RL00a conclusion.
A green job alone is insufficient. The final local matrix covers
all required cases on one recorded source; historical observations remain
separate and are not substituted for that run. Runtime distributions and
cost calibration remain RL00c work.

The spike proves cgroup primitives on the recorded host shapes. It does not
prove arbitrary containers, aarch64, nonzero time namespaces, hostile same-UID
isolation, framework worker allocation, nested `quality` CLI integration,
per-case attribution, selective-case completeness, canonical native semantics,
release thresholds or export onboarding. Those obligations remain in RL00b/c
and RL01–RL06. Product memory enforcement is still absent.
