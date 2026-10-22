# Frontend extension plan

This plan extends the completed quality boilerplate with React + Vite +
TypeScript browser applications. It follows the base
[implementation plan](PLAN.md), whose phases P00–P12 are complete and whose
records stay unchanged. The assignment is external user input and is not
part of the template; requirement IDs `FR01`–`FR10` come from it and are
restated in the [frontend traceability matrix](docs/plan/frontend/traceability.md).

## Status

- Base: `BASE_COMPLETE_SHA` is
  `dfb232208b41f8423bd74c5e1724865f199aa455` (see the
  [F00 record](docs/plan/frontend/F00.md#base))
- Current phase: F00
- Next action: commit the F00 records, then record the commit in a separate
  progress commit
- Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `NOT_VERIFIED`, `DONE`
- A box is checked only after its implementation commit exists and its checks
  ran; the phase record holds the SHA and the evidence.

## Phases

| Done | Phase | Status | Record |
| --- | --- | --- | --- |
| [ ] | F00 Verify the completed base and establish the extension plan | IN_PROGRESS | [F00](docs/plan/frontend/F00.md) |
| [ ] | F01 Extend the schema and register the browser variant | TODO | |
| [ ] | F02 Prepare the frontend environment and startup operations | TODO | |
| [ ] | F03 Implement static checks and production building | TODO | |
| [ ] | F04 Implement component unit coverage in the strict commit gate | TODO | |
| [ ] | F05 Implement production browser scenarios and accessibility | TODO | |
| [ ] | F06 Integrate the existing CLI and portable CI | TODO | |
| [ ] | F07 Prove reuse and publish bounded local documentation | TODO | |
| [ ] | F08 Complete regression verification and handoff | TODO | |

## Tasks

### F00

- [ ] Inspect the base, record `BASE_COMPLETE_SHA`, reproduce its principal
  checks
- [ ] Plan, decisions [0017](docs/decisions/0017-browser-frontend-profile.md)
  and [0018](docs/decisions/0018-browser-builds-and-scenarios.md), and the
  FR traceability with the affected R requirements
- [ ] Compatible versions from primary sources; scope and extension points

### F01

- [ ] `target`, `framework`, `bundler`, the browser table, and the `example`
  role in the policy schema, with validation and no migration
- [ ] Activation and discovery tests: browser versus Node, ambiguity,
  ownership, dormant and modified examples and helpers
- [ ] `component add --target` with React/Vite recognition, ambiguity, and
  unsupported frameworks
- [ ] A browser component fails explicitly until its checks exist

### F02

- [ ] Browser package pins and the pinned Chromium; bootstrap and doctor
  report the browser and its Linux libraries
- [ ] The registration steps of the frontend Quick start, before the CLI is
  on `PATH`
- [ ] Tests: idempotence, missing prerequisites, browser mismatch, preserved
  user configuration and hooks

### F03

- [ ] The reference application as an `example` component
- [ ] Type check, React lint rules, structure, import boundaries, CSS, HTML
  entry points, classification
- [ ] The isolated production build with its evidence
- [ ] Negative cases with their controls

### F04

- [ ] jsdom unit suites with the base floors; unimported files, conditional
  JSX, awaited interactions, ownership, unit/E2E separation
- [ ] Staged versus work tree cases, first commit, alternate index

### F05

- [ ] The owned server and Playwright through the scenario registry
- [ ] Console, resource, accessibility, and keyboard evidence
- [ ] Negative cases: stale output, unrelated server, startup failure,
  missing browser, broken assets, empty scans, skipped and focused tests

### F06

- [ ] Stage matrix, reports, the `browser` job, and the aggregate
- [ ] GitHub and GitLab wrappers and control files; verdict tests

### F07

- [ ] Fresh export, frontend Quick start, repeated bootstrap, adding a
  frontend; Node-only, frontend-only, two frontends, mixed
- [ ] Documentation within the limits

### F08

- [ ] Full regression of the frontend and base profiles; the handoff; the
  final progress commit

## Resumption

Inspect `git status` and `git log`, read this file and the last phase record,
check that its recorded SHA exists, and continue from the first unchecked
task. The protocol of the [base plan](PLAN.md#execution-protocol) applies:
implementation commit first, then a separate progress commit that names it.
