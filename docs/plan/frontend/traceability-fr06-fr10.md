# Frontend requirement traceability (FR06–FR10)

Continued from [FR01–FR05](traceability.md), with the same status values.

## FR06 Browser scenarios

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| FR06.1 | The existing scenario registry records component, capability, ID, level, boundary, and stage; startup and critical flows required | F05 | [F05](F05.md): `scenarios/test_validate.py` (the boundary of every browser scenario), `scenarios/test_reconcile.py`, `cli/test_verdict.py` (the tested boundaries); the example's `ui.smoke` and `ui.flows` scenarios | DONE |
| FR06.2 | Playwright against the isolated production output: owned server, assigned port, isolated contexts, cleanup; no reused or development server | F05 | [F05](F05.md): `typescript/test_serve.py`, `test_playwright.py`, `test_endtoend.py`; `acceptance/test_browser_scenarios.py` (a stale `dist/`, an unrelated server named by the component's `baseURL` and `webServer`), `test_browser_runs.py` (no process or temporary file left) | DONE |
| FR06.3 | Chromium required; missing binaries, failed startup, crashes, and absent reports fail; console errors and failed loads block with narrow exceptions | F05 | [F05](F05.md): `test_browser_runs.py` (no browser), the start, crash, configuration, console, asset, and response cases of `test_browser_scenarios.py`, the excepted console error; `typescript/test_playwright.py` (no report). A crash after a test's last step is not detected | DONE |
| FR06.4 | Missing mappings, skips, expected failures, focused, empty, stale, or quarantined results cannot satisfy; retries 0; flaky reported | F05 | [F05](F05.md): `testing/test_playwright.py` (the worst viewport, a focused run), `scenarios/test_reconcile.py`; the skipped, one-viewport, and focused cases and the overridden `retries` of `test_browser_scenarios.py` | DONE |
| FR06.5 | Reference application: navigation, form, CSS Modules, asset, success/loading/error, narrow and wide viewports; API fixture boundary reported | F05 | [F05](F05.md): `examples/web` as `example-web`, 4 of 4 scenarios proved in both viewports with both boundaries printed | DONE |

## FR07 Accessibility and budgets

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| FR07.1 | Static JSX accessibility rules plus axe scans of declared states and keyboard/focus scenarios | F03, F05 | [F03](F03.md): the `jsx-a11y-x` rules; [F05](F05.md): `typescript/test_scans.py`, the counter's and the example's scans and keyboard scenarios | DONE |
| FR07.2 | Serious and critical block; moderate, minor, and incomplete reported; tags and exceptions recorded; a missing scan or empty page fails | F05 | [F05](F05.md): `typescript/test_scans.py`, `policy/test_browser.py` (`accessibility_tags`), `scenarios/test_reconcile.py` (`scenarios.evidence`); the empty-page and low-contrast cases | DONE |
| FR07.3 | Names and labels, keyboard operation, focus on form errors; a failing fixture and its control | F05 | [F05](F05.md): the example's keyboard scenario (tab order, focus on the first problem, accessible descriptions); the low-contrast control of the example and of the counter | DONE |
| FR07.4 | Budgets only as explicit enhanced capabilities; nothing claimed when not run | F05, F07 | [Decision 0018](../../decisions/0018-browser-builds-and-scenarios.md#accessibility): no budget is part of the baseline; the F07 documentation keeps it so | IN_PROGRESS |

## FR08 Stages and CI

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| FR08.1 | Commit stage: common gates, static checks, type check, unit suites with 80/70/90 over the index | F04, F06 | [F04](F04.md): `acceptance/test_browser_units.py`, `test_browser_candidate.py` (the hook of a commit of named paths); [F06](F06.md): both lanes at the commit stage in `engine/test_lanes.py`, the stage table of decision 0018 | DONE |
| FR08.2 | Merge stage: all of that again, build, Chromium scenarios, accessibility, audit, history | F05, F06 | [F05](F05.md): `quality gate --stage merge` in `acceptance/test_browser_runs.py` with its native evidence; [F06](F06.md): the browser lane at the merge stage on the host and in the pinned Ubuntu image | DONE |
| FR08.3 | Maintainer validation: helper gates, frontend acceptance, and regression acceptance of the base profiles | F06, F08 | Planned: the F08 merge gate | TODO |
| FR08.4 | Full validation outside CI; thin wrappers; a failed, cancelled, missing, or skipped frontend job fails the aggregate | F06 | [F06](F06.md): `ci/test_verdict.py`, `ci/test_lanes.py`, `test_ci_wrappers.py` (the real policy and workflow with each result of the `browser` job), scenario `browser-lanes` without provider variables, the container run | DONE |
| FR08.5 | Browser jobs only for relevant scopes; the maintainer repository exercises them; control files cover the new settings; hosting prepared only | F06 | [F06](F06.md): the browser lane checks only active browser components, here `example-web`; `ci/test_control.py` (the browser settings), `ci.lanes`; hosting prepared, not observed | DONE |

## FR09 Quality of the extension

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| FR09.1 | New orchestration, server, report, and helper code under the base rules and coverage | All | Planned: each phase's hook run | TODO |
| FR09.2 | Unit tests for failure paths and real native acceptance; invalid fixtures generated or bounded | All | Planned: each phase's tests | TODO |
| FR09.3 | No recursive harness; exported fixtures get a new Git repository with a test identity | F07 | Planned: template acceptance | TODO |
| FR09.4 | A regression for every defect found; logs, traces, and screenshots outside tracked source, redacted | All | Planned: phase records | TODO |

## FR10 Compatibility and readiness

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| FR10.1 | Startup for frontend-only, Node-only, and mixed projects and for adding a frontend; fresh history; repeated bootstrap; no browser for other projects | F07 | Planned: template acceptance | TODO |
| FR10.2 | Documentation limits, English, links, exceptions, the blob limit, dependency checks; supported versus unsupported variants | F07 | Planned: the docs gates | TODO |
| FR10.3 | A handoff with SHAs, contracts, versions, commands, evidence, regressions, limitations, and hosting; no readiness claim while anything is unverified | F08 | Planned: the frontend handoff | TODO |

## Affected base requirements

The base contract stays in force; these rows say what the extension adds to
each requirement and where it is proven again. The rest keep their P12
proof unchanged.

| IDs | Effect of the extension | Phases | Status |
| --- | --- | --- | --- |
| R01.1, R07.3, R07.4, R07.9 | The TypeScript profile gains the browser target; the four Tier 1 profiles are proven again | F03–F05, F08 | IN_PROGRESS |
| R01.2 | Unsupported frontend frameworks and variants are reported like Flutter | F01 | DONE |
| R01.4 | The `example` role and activation by target | F01 | DONE |
| R01.6 | The core adds no package manager or framework; Vite, Playwright Test, and Stylelint are the ecosystem's tools that FR02 requires, installed by npm from the lock | F02 | DONE |
| R01.7, R01.8 | New helper and core code at the component floors; mocked unit tests plus real acceptance | All | TODO |
| R02.1, R02.4, R02.5 | `component add --target`; the pinned browser with checksums, set up only for active browser components | F01, F02 | DONE |
| R02.2 | Generated Vite and Playwright wrappers override what decides the verdict | F03, F05 | DONE |
| R03.1–R03.11 | Snapshot and revision semantics proven with frontend files | F04, F05 | DONE |
| R04.1–R04.7 | Limits unchanged; formatter and lint sets extend to CSS and HTML; asset blob and secret checks; browser/server boundaries | F03, F04 | DONE |
| R05.1–R05.7 | Frontend documentation within the limits | F07 | TODO |
| R06.1–R06.11 | Per browser component, unchanged floors and evidence rules | F04 | DONE |
| R07.1 | Compatible versions from primary sources: [decision 0017](../../decisions/0017-browser-frontend-profile.md#versions) | F00 | DONE |
| R08.1–R08.7 | The `ui` capability of a browser component, the scenario boundary, and viewports | F05 | DONE |
| R09.1–R09.8 | The `browser` job in the wrappers and the aggregate | F06 | DONE |
| R10.1–R10.7 | Export, documentation, regressions, and the handoff | F07, F08 | TODO |
