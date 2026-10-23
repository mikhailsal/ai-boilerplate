# Frontend extension handoff

This page closes the frontend extension, phases F00–F08 of the
[frontend plan](../../../FRONTEND_PLAN.md), which added React + Vite +
TypeScript browser applications to the completed boilerplate. It is a
bounded summary; the phase records and the traceability matrices
([FR01–FR05](traceability.md), [FR06–FR10](traceability-fr06-fr10.md)) hold
the evidence behind each line. It is the author's record, not an
independent audit.

## Audit remediation (2026-10-23)

The independent audit and remediation started at the same revision,
`5ab0146002d1a33afde8c5dbeb29ae784dd0df91`, with a clean working tree.
The remediation branch is `fix/audit-2026-10-22`;
[pull request #3](https://github.com/mikhailsal/ai-boilerplate/pull/3)
targets `build/frontend`, the branch of the original frontend pull request #2.
The original F08 status and verification below are historical records.

| Finding | Status | Implementation commit | Reproduction and regression |
| --- | --- | --- | --- |
| AUD-001 | Fixed | `cce1358b6e8fc924f46331dbf301f51602d27e9a` | The original rogue proxy proved 4 of 4 scenarios without candidate content. Routing settings now fail with `typescript.playwright`; each passing test needs an owned document response, and substituted pages fail with `typescript.browser-served`. Legitimate presentation settings still pass. |
| AUD-002 | Fixed | `b4fb46f0a6e395d93e906aeb60441043272c8003` | Root and workspace manifest drift now produce `typescript.lockfile`, exit 1, before installation. Matching locks pass offline; genuine cache misses retain exit 3. |
| AUD-003 | Fixed | `6701b94d84a33453ac948712725d2dc5c3839178` | Python registration supplies the absent interpreter pin, preserves existing pins, and the first commit passes the real hook. |
| AUD-004 | Fixed | `0de751da2d3859d87915c1d672e2aff7e2688ffb` | The valid GitLab wrapper passes without `[ci]`; deleted, relabelled, or unresolved browser lanes fail with `ci.lanes`. Local inheritance and variables are resolved. |
| AUD-005 | Open: hosting prerequisite | No implementation commit | Read-only GitHub observations still show no rulesets and no protection on `main`. Applying hosting settings needs separate authorization. GitLab hosted execution remains unverified. |

Final review also covered dangling interpreter-pin symlinks and browser
interruption. The symlink follow-up is `2ff8da90e48845c6011778e225f5d711b3c23708`; it preserves
the link without creating its external target. The browser cleanup
follow-up is `0e544c157cdbc16fcd692bf77f33f59bfb97d388`. Before that fix, terminating the worker
left 15 owned Node/Chrome processes. Native regressions now verify cleanup
after worker termination, CLI interruption, and a timeout with a detached
child that ignores SIGTERM. The worker checks pidfd support before launch
and reaps its descendants on every exit; see
[decision 0018](../../decisions/0018-browser-builds-and-scenarios.md).

The GitLab include follow-up is `d9b32b6e51fd1bdf963293c05fe0b5bf4bf007c1`. It validates
the known local wrapper after applying root overrides, including normalized
path aliases. Missing wrappers and unresolved compositions block with
`ci.lanes`.

The final verification record is maintained in pull request #3. Its source
provenance, command results, native artifacts, hook logs, and finding/commit
ledger are retained at
`/home/tass/myprojects/corp_v2/audit-remediation-2026-10-23/`.
`verification.json` names the exact tested revision and each command's exit
status; `evidence/final/completed.json` is written only after every required
step passes. The sequence covers fresh-cache bootstrap, doctor, policy,
scenario and schema validation, the full check, all three self-test levels,
and exported browser, Python first-commit, and history controls. No threshold,
exclusion, mandatory scenario, or installed Git hook was weakened.

Passing local checks and hosted CI do not apply branch protection. AUD-005
therefore remains open independently of the implementation results.

## Original F08 status

- Base: `BASE_COMPLETE_SHA` is `dfb232208b41f8423bd74c5e1724865f199aa455`,
  the completed base handoff ([F00](F00.md#base)).
- Phases F00–F08 are `DONE`; each record lists its commits, checks, and
  limitations.
- Final implementation commit: `4d597a75bb6abbb3923326238e17bcf68aff7a0f`
  on `build/frontend`. The commit that adds this page records the
  completion and changes no code.
- Requirements: every FR and extended R row of the matrices is `DONE` with
  its proof.
- Hosting: with the user's approval, F08 pushed `build/frontend` and opened
  draft pull request #2, whose run is the regression of record; see
  [Hosting](#hosting).

## Changed contracts

| Contract | Change |
| --- | --- |
| Policy (`quality.toml`, `policy.schema.json`) | A TypeScript component's `target` (`node` or `browser`), `framework = "react"`, `bundler = "vite"`, and `[components.browser]` (entries, public values, server modules and packages, viewports, `accessibility_tags`); the `example` role; a scenario's `boundary`; `ui.accessibility` and `ui.keyboard` for browser components only; `[ci].required_jobs` adds `browser` |
| Pins (`toolchains.toml`) | `[tools.chromium]`, the Chrome for Testing headless shell with SHA-256 pins for x86_64 and aarch64; `[packages.npm-browser]`, which a browser component's lockfile must lock exactly |
| CLI | `component add --target node\|browser`, which refuses ambiguous and unsupported projects and registers a browser application's `e2e` suite and `scenarios.toml`; `--e2e` and `--scenarios`; `gate --lane main\|browser`, with the lane in `report.json` |
| Rules | `typescript.browser-libraries`, `-version`, `-ready`, `typescript.boundaries`, `typescript.styles`, `typescript.entries`, `typescript.build`, `typescript.build-output`, `typescript.browser-console`, `typescript.browser-resource`, `typescript.accessibility`, `typescript.accessibility-scan`, `scenarios.evidence`, `gate.lane`, `ci.lanes` |
| CI | An unconditional `browser` job in the GitHub workflow and the GitLab wrapper; the aggregate `required` status needs `gate`, `browser`, and `audit` |
| Template | The reference application `examples/web`, exported and dormant until changed; the README's browser Quick start |

Decisions [0017](../../decisions/0017-browser-frontend-profile.md) and
[0018](../../decisions/0018-browser-builds-and-scenarios.md) are the
design; 0002, 0011, 0014, and 0015 were amended, and both generated schemas
were regenerated.

## Versions

The browser pins and their compatibility evidence are in
[decision 0017](../../decisions/0017-browser-frontend-profile.md#versions):
React 19.3.1, Vite 8.3.5 with `@vitejs/plugin-react` 6.1.2, jsdom 30.1.3,
Testing Library 16.3.3, Stylelint 17.16.0, `eslint-plugin-react-hooks`
7.1.1, `eslint-plugin-jsx-a11y-x` 0.2.0, `@playwright/test` 1.64.1,
`@axe-core/playwright` 4.14.0, and the Chrome headless shell
156.0.8078.4. Every pin of the base stays, including Node.js 24.22.0,
TypeScript 6.0.3, ESLint 10.13.0, and Vitest 5.0.5. The host is the one of
the base handoff: Linux 5.15 x86_64, Git 2.34.1, system `python3` 3.10.12.

## Start

From a project exported with `./quality template export ../my-project`, on
Linux with Git 2.34+ and `python3` 3.10+, and for a browser component the
Chromium libraries of
[decision 0002](../../decisions/0002-installation-strategy.md#prerequisites-documented-not-promised-away):

```sh
./quality bootstrap
git archive --prefix=apps/web/ HEAD:examples/web | tar -x
rm apps/web/README.md
sed -i 's/^component = "example-web"$/component = "web"/' apps/web/scenarios.toml
./quality component add apps/web --target browser
git add quality.toml apps/web
./quality bootstrap
git commit -m "Add the web application"
./quality test --component web --suite unit --suite e2e
```

`./quality` is the first invocation; nothing has to be on `PATH`. A
TypeScript Node or other backend component is added with
`./quality component add <dir>` as in the
[README](../../../README.md#getting-started), before or after the frontend.
CI runs `./quality gate --lane main`, `./quality gate --lane browser`, and
`./quality audit`; locally, `./quality gate --stage merge --base main --head
HEAD` runs both lanes.

## Verification

The regression of record is run 39802757156 of the `quality` workflow on
GitHub for draft pull request #2 at `4d597a7`
([F08](F08.md#the-hosted-run)). `required` passed over `gate`, `browser`,
and `audit`, with 0 errors and the 4 warnings of the base. Every unit suite
passed with line and branch coverage of 100%: the core 2796 tests, the
launcher 64, the three helpers 66, 73, and 65, and `example-web` 14. The
core's acceptance suite passed 203 of 203: the cases of the base profiles,
Python with the common gates 36, TypeScript Node 21, Dart VM 26, and PHP 29;
mixed projects and scenario runners 27; browser applications 57; the
template and Quick start 7. The core proved its 9 scenarios, the launcher
2, and `example-web` 4 in both viewports.

On this host the pre-commit hook passed for every implementation commit,
and the release commands passed at `4d597a7`: the audit, the link probe,
the policy and schema checks, doctor, and the scenario manifests. The full
merge gate failed at `771f33d`, because seven whole-gate acceptance tests
overcommitted the CPUs; `4d597a7` limits them to one per two CPUs. Its
re-run was stopped for lack of memory on this shared machine, so it has no
result.

## Hosting

| Item | Prepared | Observed on the host |
| --- | --- | --- |
| GitHub `gate`, `browser`, and `audit` jobs and the `required` aggregate | Validated locally: actionlint, the CI policy, the verdict over failed, cancelled, skipped, and missing jobs | Observed for a pull request: run 39802757156 passed. `merge_group` and `push` events: `NOT_VERIFIED` |
| Ruleset `.github/rulesets/main.json` and code owners | As in the base | `NOT_VERIFIED`: not applied |
| GitLab wrapper | Its `before_script`, both lanes, the audit, and the verdict passed in a clean `ubuntu:24.04` container ([F06](F06.md)) | `NOT_VERIFIED`: never run on GitLab |
| Draft pull request #1 | Opened for the base | Its last three runs, at `dfb2322` among them, failed while installing PHP, when Launchpad's PPA answered 503 |

## Known limitations

- Supported is one variant: a client-rendered React + Vite single-page
  application tested in jsdom and the pinned Chromium on Linux glibc.
  Server rendering, other frameworks and bundlers, Vitest Browser Mode,
  Firefox, WebKit, and visual, bundle-size, or performance budgets are not
  ([profile matrix](../../reference/profiles.md#browser-applications)).
- The Chromium libraries are a host prerequisite; bootstrap checks them
  (`typescript.browser-libraries`) but installs nothing. The GitHub job
  relies on the runner image.
- Google publishes no SHA-256 for the headless shell: the pins were computed
  after the MD5 digests of the bucket matched, and `quality tools update`
  refuses Chromium, which moves by hand with Playwright.
- `eslint-plugin-jsx-a11y-x`, a maintained fork, replaces
  `eslint-plugin-jsx-a11y` until a release accepts ESLint 10.
- GHSA-vfj7-8cjw-p6xm in `braces` 3.0.3 has no fixed release; the template's
  two lockfiles carry exceptions that expire on 2027-01-22, and a project's
  copy of the reference application needs its own.
- Browser jobs run for every active browser component, not per affected
  change, and this repository's main lane needs Chromium for the core's
  acceptance suite.
- A renderer crash after a test's last step is not detected, and incomplete
  axe results are reported only as information.
- Without unprivileged user namespaces, as in an unprivileged container,
  each unit suite warns with `tests.network`.
- The base handoff's limitations still apply: bypassable local hooks,
  protection that is prepared but not applied, and the cost of core changes.
- The full merge gate of this repository needs several gigabytes of free
  memory and an hour on eight CPUs; on a shared machine it can be stopped
  before it ends, as in F08.

## Review entry points

- The README's [browser Quick start](../../../README.md#a-browser-application)
  and the [profile matrix](../../reference/profiles.md#browser-applications).
- Decisions 0017 and 0018; the reference application under `examples/web`.
- The adapter under `tools/quality/src/quality/adapters/typescript`,
  starting at `profile.py`, `browser.py`, `endtoend.py`, and `chromium.py`;
  the lanes in `ci/lanes.py` and `engine/check.py`.
- The acceptance modules `test_browser_*.py` and `test_frontend_start.py`.
