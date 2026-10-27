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
- Current phase: none; F00–F08 are complete, and the
  [frontend handoff](docs/plan/frontend/handoff.md) summarizes the result
- Next action: none
- Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `NOT_VERIFIED`, `DONE`
- A box is checked only after its implementation commit exists and its checks
  ran; the phase record holds the SHA and the evidence.

## Phases

| Done | Phase | Status | Record |
| --- | --- | --- | --- |
| [x] | F00 Verify the completed base and establish the extension plan | DONE | [F00](docs/plan/frontend/F00.md) |
| [x] | F01 Extend the schema and register the browser variant | DONE | [F01](docs/plan/frontend/F01.md) |
| [x] | F02 Prepare the frontend environment and startup operations | DONE | [F02](docs/plan/frontend/F02.md) |
| [x] | F03 Implement static checks and production building | DONE | [F03](docs/plan/frontend/F03.md) |
| [x] | F04 Implement component unit coverage in the strict commit gate | DONE | [F04](docs/plan/frontend/F04.md) |
| [x] | F05 Implement production browser scenarios and accessibility | DONE | [F05](docs/plan/frontend/F05.md) |
| [x] | F06 Integrate the existing CLI and portable CI | DONE | [F06](docs/plan/frontend/F06.md) |
| [x] | F07 Prove reuse and publish bounded local documentation | DONE | [F07](docs/plan/frontend/F07.md) |
| [x] | F08 Complete regression verification and handoff | DONE | [F08](docs/plan/frontend/F08.md) |

## Tasks

### F00

- [x] Inspect the base, record `BASE_COMPLETE_SHA`, reproduce its principal
  checks
- [x] Plan, decisions [0017](docs/decisions/0017-browser-frontend-profile.md)
  and [0018](docs/decisions/0018-browser-builds-and-scenarios.md), and the
  FR traceability with the affected R requirements
- [x] Compatible versions from primary sources; scope and extension points

### F01

- [x] `target`, `framework`, `bundler`, the browser table, and the `example`
  role in the policy schema, with validation and no migration
- [x] Activation and discovery tests: browser versus Node, ambiguity,
  ownership, dormant and modified examples and helpers
- [x] `component add --target` with React/Vite recognition, ambiguity, and
  unsupported frameworks
- [x] A browser component fails explicitly until its checks exist

### F02

- [x] Browser package pins and the pinned Chromium; bootstrap and doctor
  report the browser and its Linux libraries
- [x] Tests: idempotence, missing prerequisites, browser mismatch, preserved
  user configuration and hooks

### F03

- [x] Type check, React lint rules, structure, import boundaries, CSS, HTML
  entry points, classification
- [x] Negative cases of the static checks with their controls
- [x] The isolated production build with its evidence and negative cases
- The reference application moved to F05, where its checks can pass (see
  the [F03 record](docs/plan/frontend/F03.md#scope))

### F04

- [x] jsdom unit suites with the base floors; unimported files, conditional
  JSX, awaited interactions, ownership, unit/E2E separation
- [x] Staged versus work tree cases, first commit, alternate index

### F05

- [x] The reference application as an `example` component
- [x] The owned server and Playwright through the scenario registry
- [x] Console, resource, accessibility, and keyboard evidence
- [x] Negative cases: stale output, unrelated server, startup failure,
  missing browser, broken assets, empty scans, skipped and focused tests

### F06

- [x] Stage matrix, reports, the `browser` job, and the aggregate
- [x] GitHub and GitLab wrappers and control files; verdict tests

### F07

- [x] Fresh export, frontend Quick start, repeated bootstrap, adding a
  frontend; Node-only, frontend-only, two frontends, mixed
- [x] The registration steps of the frontend Quick start, before the CLI is
  on `PATH`
- [x] Documentation within the limits

### F08

- [x] Full regression of the frontend and base profiles; the handoff; the
  final progress commit

## Resumption

Inspect `git status` and `git log`, read this file and the last phase record,
check that its recorded SHA exists, and continue from the first unchecked
task. The protocol of the [base plan](PLAN.md#execution-protocol) applies:
implementation commit first, then a separate progress commit that names it.
