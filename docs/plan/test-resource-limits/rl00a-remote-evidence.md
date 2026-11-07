# RL00a: remote verification and directory-removal evidence

Status on 2026-11-08: the amended resource workflow passed all 26 pairs on
GitHub Actions. Its stronger directory-removal obligation remains unproved
by the original driver, so RL00a completion is not declared from that result.
The follow-up driver records and requires actual removal within the original
deadline; its remote validation is pending.

## Observed remote matrix

[Run 42417505280, attempt 1](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42417505280)
tested `165ef689d97976b7a353ac3a51bcfb19a0bc484c` on the Ubuntu 24.04 runner,
Linux 7.0.0-1017-azure, x86_64 and Python 3.12.3. All 26 unique host/prepared
pairs and all 26 unrelated sentinel observations passed. All eight captured
source files match that commit and the frozen
[local cache-split inputs](rl00a-cache-split-evidence.md), including the hidden workflow.

The [artifact](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42417505280/artifacts/13591589451)
has verified ZIP SHA-256
`2bc794a3351006c6aaf0de2e601b65c0feb96b16cf1c63bec0e06c24fdb15aba`.
Both dirty writers received native SIGKILL with own-leaf OOM evidence and were
classified as resource violations. Both separate reclaim fixtures completed
with native zero, no OOM, 40 MiB written/read, ten fsyncs and held-file residency
evidence. File-refault deltas were 10,240 and 10,241 across the entire leaf;
these are corroboration, not exact per-inode counts.

Own/ancestor attribution, fixed role/task/swap caps, partial setup, nested
deadlines, expected death outcomes and invocation cleanup were independently
audited. Kill-to-empty measurements were approximately 0.019–5.15 ms and
excluded detection/reporting. Recorded residual charge before removal was
sometimes nonzero. The host dirty writer's kernel peak exceeded its 32 MiB
readback ceiling by 4 KiB; this remains a kernel-semantic limit, not an exact
zero-overshoot guarantee.

## Remaining observation and targeted correction

Guardian-death fallback completed in approximately 1.273 and 1.262 seconds,
but the old driver recorded only `root_empty_or_removed`. That boolean cannot
distinguish an existing empty directory from an actually removed service root.
The protocol requires removed owned directories; a green job does not repair
that evidence gap.

The follow-up changes only the driver's observation: it retains provider path
and inode, proxy status, separately observed `populated=0` and actual root
absence, and the observation times in `service-cleanup.json`. Each present
root must retain its provider inode. Actual removal must be observed before
the earlier of the original six-second deadline and the existing two-second
cleanup bound; observing emptiness does not restart the timer. Missing evidence
or late removal is a nonpass. The original provider, guardian, payloads,
placement primitives, workflow and numerical limits are unchanged.

## Remote-only execution

After local CPU load interrupted publication, the owner explicitly requested
all heavy checks in CI and permitted `--no-verify` for commit/push operations
within this task. Installed hooks and repository policy were not changed.
The earlier local 26-pair observation remains bound to revision `165ef689`;
it does not certify the follow-up driver's new observation. No further local
stress, unit or full quality runs are used for this correction.

[Draft PR 8](https://github.com/mikhailsal/ai-boilerplate/pull/8) triggers the
existing full `quality` workflow: main lane, browser lane, advisory audit and
aggregate required status. The separate `resource-proof` workflow must retain
all 26 pairs, all eight source inputs and the new directory-removal records.
No merge, deployment, production enforcement or later RL00 work is claimed.
