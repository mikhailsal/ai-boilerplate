# RL00a: remote verification and directory-removal evidence

Status on 2026-11-08: RL00a is technically complete within the environment and
observation limits below. The final remote matrix proves directory removal within
the existing deadline. Earlier failed observations and the original driver gap
remain part of the record. RL00b and RL00c are unperformed.

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

## Final remote proof

The directory-observation revision passed its resource matrix but its normal
quality run failed Pyright on a numeric comparison through a heterogeneous
evidence dictionary. The subsequent revision computes the same duration in a
float local before storing it; the expression, assertions, deadlines and caps
remain unchanged. No local validation was run for the final driver.

[Resource run 42421777851](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42421777851),
job `128551544721`, tested commit `50f7c1bf887d78859c7d949f333d2ef12dfc7718`.
Its independently audited [artifact](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42421777851/artifacts/13593742505)
has ZIP SHA-256 `6cbd9cc8a2123c89c141e5d3638e5f0ab0e5593792ad3b1eddd065bd009cdcb4`.
All eight captured sources match the commit and expected inputs; all 26 pairs
passed, unrelated sentinels survived, and all service roots were observed absent
before their deadlines. The minimum observed deadline margin was approximately
0.673 seconds. Absence observation is an upper bound on removal time. Guardian
cleanup timing excludes detection, and residual charges were nonzero in the
recorded range. File-refault counts are leaf-wide, not per-inode measurements.

The [normal quality run 42421781481](https://github.com/mikhailsal/ai-boilerplate/actions/runs/42421781481)
passed its required job `128562795632` for the merge candidate with that head.
Its main reports contain 3,518 tests with no failures or skips, five unit reports
with 100% line and branch coverage, and 11 of 11 required scenarios proved.
The earlier local `165ef689` baseline does not execute the final driver or prove
local guardian-root removal within the deadline. The final removal proof is CI
only, consistent with the owner's remote-only instruction; it does not establish
behavior on every supported host. RL00a does not prove per-case attribution,
useful verdicts, overhead, onboarding or integration readiness.
