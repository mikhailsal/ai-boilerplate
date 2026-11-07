# RL00a: bounded kernel feasibility protocol

Execution authorized by the owner's active RL00a goal on 2026-11-06. This
experiment does not integrate resource limits into `quality`. RL00b/c and
production policy values remain outside its claim. Live GitHub publication
requires review of the concrete workflow and a separate owner approval, as
required by [the verification plan](verification.md).

## Subjects and finite experimental fixtures

The subject is kernel-charged memory in an owned cgroup subtree, including
anonymous, native and charged file-cache pages. This is neither physical RSS
nor a per-test attribution method. Swap is explicitly disabled in every owned
boundary. `memory.current` samples are lower bounds on observed peaks;
`memory.peak`, when absent, is unavailable. Record local and hierarchical
events before and after each workload. An own OOM/denial is a violation even
when native code catches it; successful cache reclaim alone is not one.

The following are finite experiment fixtures, not proposed project thresholds:

- Run cases serially. Each transient service has 256 MiB, zero swap, 64 tasks,
  a 16-second runtime backstop and a one-second systemd stop grace period.
- A 32 MiB / 8-task independent guardian and a 224 MiB / 48-task invocation
  divide that total. The invocation contains a 32 MiB / 8-task supervisor leaf
  and a 160 MiB / 32-task payload branch, leaving 32 MiB unassigned headroom.
- Each supervisor has a six-second absolute monotonic deadline: stop payload
  at four seconds and reserve two seconds for cleanup/reporting. The guardian
  independently enforces it. CLOCK_MONOTONIC excludes suspend; time-namespace
  identity and offsets are recorded. A namespace mismatch fails before payload.
- Individual allocation requests never exceed 80 MiB. Fork probes attempt at
  most 16 children, all with an eight-second independent lifespan. Other
  payloads also stop independently within eight seconds.
- One unrelated sentinel service (32 MiB, eight tasks, at most 300 seconds)
  remains alive during the proof. The two services' combined ceilings are
  288 MiB. Require at least 512 MiB available host memory before each case;
  unavailable capacity is an environment nonpass, never an unprotected retry.

## Provisioning and independent enforcement

Both paths use cgroup v2 with `memory`, `pids`, `cgroup.kill` and writable
delegation. The ordinary-host path obtains a fresh systemd delegated unit;
the runner creates its own invocation branch. For the prepared path, a
separate provider prepares the empty limited branch before handing its open
descriptor to the runner. The runner does not call systemd or sudo.

The provider/guardian occupies a separate bounded leaf and observes the
supervisor through a pidfd. Supervisor death or expiry closes admission and
kills the verified invocation subtree. systemd `KillMode=control-group`, a
one-second stop grace and `RuntimeMaxSec` independently cover guardian death
and an unresponsive guardian. The prepared-path fixture uses this same
external provider contract; it does not claim arbitrary containers supply it.
Payloads run as the ordinary user. CI's system-manager provisioning may use
sudo to create, inspect and stop only the experiment's UUID-named transient
services. The supervisor and payload never elevate themselves. No persistent
machine configuration changes are needed.

Empty internal branches enable controllers top-down. A separate placement
shim writes its PID through an already-open cgroup descriptor before exec;
no threaded Python `preexec_fn` is used. The first payload statement records
membership, UID, namespace and start time. Opaque generated names and
descriptor-relative, no-symlink operations constrain ownership. Environment
strings alone never authorize cleanup.

## Preregistered verdicts

| Case | Expected observation |
| --- | --- |
| placement / partial setup | All ancestor caps and membership precede payload exec; rejected oversized setup starts no payload. |
| own memory | A 32 MiB leaf rejects an 80 MiB request; leaf-local OOM evidence, supervisor and sentinel survive. |
| ancestor memory | Two bounded leaves fit individually but exhaust their 96 MiB parent; parent-local cause, no invented offending case. |
| nested budgets | Two nested branches retain memory/task ceilings and the original deadline; oversized requests fail promptly while parents remain charged. |
| caught task denial | A two-task leaf catches EAGAIN and exits zero; `pids.events` still proves a resource violation. |
| dirty cache | Retain the original 40 MiB writer under 32 MiB. Native zero without own/ancestor OOM is native success; SIGKILL requires matching own-leaf OOM and kill events with no ancestor-local OOM, and remains a resource violation. Unexpected statuses or mismatched evidence are nonpasses. |
| cache reclaim | A separate 40 MiB anonymous disk-file workload under 32 MiB fsyncs every 4 MiB and must complete without OOM. Held-open file residency, charged-file snapshots and file-refault evidence must prove actual cache eviction and reread. |
| interrupt / timeout | Owned detached, signal-ignoring descendants disappear within the cleanup reserve; the sentinel survives. |
| supervisor death / OOM | A pidfd guardian survives supervisor SIGKILL or control-leaf OOM and removes all owned descendants. |
| guardian death | External driver kills the service main PID; systemd removes the entire owned subtree within its stop bound; sentinel survives. |

Every case records source hashes, kernel/runtime, cgroup inode/path, controller
and event semantics, configured/read-back caps, absolute deadlines, sampled
memory, native status, cleanup elapsed time and residual state. A nonpass or
incomplete cleanup stops the experiment; it does not relax any limit.
`cgroup.events: populated=0`, verified process lifetimes and removed owned
directories jointly establish cleanup. Uninterruptible processes are no-go.

Run the opt-in maintainer harness with:

```sh
python3 tools/quality/tests/acceptance/rl00a/rl00a_driver.py \
  --manager user --output .gstack/tmp/rl00a-local
```

These standalone acceptance helpers are not collected by ordinary pytest:
they require explicit delegation and exercise intentional OOM/death. Existing
Ruff, Pyright, structure, secrets and policy checks still cover retained files.
The raw evidence stays private or in the CI artifact; a concise evidence
report links exact source/workflow identities. Readbacks, fake cgroupfs tests
and a green job without the required evidence cannot establish feasibility.

Kernel semantics: [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html).
Provider fallback: [systemd kill procedure](https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html)
and [resource control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html).

## Recorded fixture amendment before the final local run

The initial 80 MiB / 64 MiB cache fixture hit I/O writeback latency: one
attempt completed in 2.16 seconds; another wrote only 67.6 MiB before the
original four-second cutoff. Both attempts remain in the evidence history.
The final fixture halves both file size and cap, retaining the same pressure
ratio and requiring observed reclaim plus successful completion. No session
deadline or project threshold increases. An anonymous temporary disk file
also ensures kernel cleanup on SIGKILL rather than relying on a Python
finally block to unlink it. File progress and failed cleanup evidence are retained.

## Diagnostic amendment prepared after the first CI nonpass

The first CI observation remains a required-proof failure, as recorded in
[the evidence report](rl00a-evidence.md#first-real-ci-observation-required-proof-failed).
The resumed goal authorizes preparing and locally checking additional evidence
under the same workloads, finite caps and original absolute deadlines.
A further live workflow still needs review of its concrete revision and identity.

The cache case writes `cache-observation.json` before its success assertions
and on exceptional paths. It retains native wait/poll status, whether the child
is still live, before/after leaf snapshots with keyed `memory.stat`, and the
mount backing the artifact directory. Missing diagnostics remain explicit;
capture failures preserve an existing workload exception. A healthy workload
without required diagnostics cannot establish a pass.

The driver writes `sentinel.json` after successful and failed cases, before
stopping the independent sentinel. Observation/capture failures preserve the
original case failure; a successful case still requires proven sentinel survival.
Service-cleanup errors are logged alongside an existing case failure. A cleanup
error after an otherwise successful run remains a nonpass.
The uploader includes hidden paths in the dedicated report directory so the
captured workflow under `source/.github` is retained with the other source inputs.
That directory contains only the experiment's source copies and observations.

The dirty-file cache workload and all expected verdicts remain as preregistered.
The amendment supplies attribution evidence; it does not establish successful
reclaim, a filesystem cause, or a complete matrix without observing them.

## Owner-approved cache split after the diagnostic CI failure

The owner selected A on 2026-11-07 after reviewing
[the second real CI failure](rl00a-diagnostic-evidence.md#second-real-ci-observation).
This explicitly changes the original dirty-writer success oracle for future
runs. Both historical 24-pair attempts retain their original nonpass verdicts.
The original writer function, 40 MiB size and 32 MiB cap remain unchanged;
it becomes the required `dirty-cache` characterization. A caught or unexpected
exit cannot be silently treated as successful reclaim. Proven own OOM remains
a resource violation even when the characterization correctly detects it.

The separate required `cache-reclaim` action writes every byte of a fresh,
nonsparse anonymous disk file inside its fresh 32 MiB leaf. It flushes and
fsyncs each 4 MiB batch before continuing. The child holds the descriptor open
at `written` and `reread` checkpoints, and the supervisor captures file size,
allocated blocks, stable device/inode, zero links, keyed `memory.stat` and leaf
events. Read-only `mincore` observations of this exact file must show that
some previously written pages are no longer resident; no mapping write,
truncation or explicit cache eviction is used. Charged-file observations and
positive local max/reclaim counters accompany that file-specific evidence.
The controlled full reread must increase `workingset_refault_file` while the
file remains open. Generic reclaim counters alone cannot certify file reclaim.
The refault counter covers the whole leaf, including evidence-file activity;
it corroborates the exact-file residency observation, not a per-inode count.

Native success, all 40 MiB written/read, all ten fsyncs, zero own/ancestor OOM
and complete evidence are required. Unsupported allocation/residency evidence,
tmpfs backing, timeout or missing counters is a nonpass, never a relaxed oracle.
The barriers and instrumentation consume the original four-second payload
budget and six-second absolute deadline; the two-second cleanup reserve stays.
No runtime, memory, task or swap ceiling changes. The fixture is not a promise
that every filesystem or runner will complete it.

A complete amended matrix contains 13 cases on each of the host and prepared
paths: 26 unique pairs from one frozen source revision. All eight source inputs,
including the extracted cache helper and hidden workflow, must be captured and
hash-verified. Local proof and concrete review precede separately approved live
CI publication; this owner decision alone does not authorize another CI run.
