# RL00a: local evidence and remaining gates

Status on 2026-11-06: the final local 24-pair matrix passed; GitHub proof not run.
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

## Concrete CI experiment awaiting separate owner approval

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
[the verification plan](verification.md). A public-safe snapshot keeps the
seven proved source inputs unchanged while replacing raw local diagnostics
with this sanitized summary. The original local commit stays unpublished. The workflow content has Git blob SHA
`3ad0087f77621beecaa78f58d12cef47c1aac471`; its tested CI commit will be recorded
after publication. No GitHub run or CI pass is claimed. A failed CI observation remains evidence and stops any
claim of readiness; it is not retried automatically.

## Limits and next evidence

Before a go decision, inspect the exact CI revision, every expected pair and
the uploaded counters/cleanup evidence and record an owner-reviewed RL00a
conclusion. A green job alone is insufficient. The final local matrix covers
all required cases on one recorded source; historical observations remain
separate and are not substituted for that run. Runtime distributions and
cost calibration remain RL00c work.

The spike proves cgroup primitives on the recorded host shapes. It does not
prove arbitrary containers, aarch64, nonzero time namespaces, hostile same-UID
isolation, framework worker allocation, nested `quality` CLI integration,
per-case attribution, selective-case completeness, canonical native semantics,
release thresholds or export onboarding. Those obligations remain in RL00b/c
and RL01–RL06. Product memory enforcement is still absent.
