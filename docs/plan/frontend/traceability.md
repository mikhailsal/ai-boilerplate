# Frontend requirement traceability (FR01–FR05)

Every requirement of the frontend extension has an owner phase and a planned
proof; the `Proof` column names tests once they exist. Continued in
[FR06–FR10 and the affected base requirements](traceability-fr06-fr10.md).
The base matrix ([R01–R05](../traceability.md),
[R06–R10](../traceability-r06-r10.md)) stays as P12 left it.

Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `NOT_VERIFIED`, `DONE`.

## FR01 Component model

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| FR01.1 | Language, target, framework, bundler, ownership, and capabilities explicit in the existing schema | F01 | [F01](F01.md): `policy/test_browser.py`, the regenerated schema | DONE |
| FR01.2 | React rules, DOM globals, transforms, and test environments only in browser components | F01, F03, F04 | [F03](F03.md): `typescript/test_profile_browser.py` (browser rules and gates only for the browser target), `test_typescript_layouts.py`; [F04](F04.md): `typescript/test_runner.py` (jsdom only for a browser component) | DONE |
| FR01.3 | React/Vite recognized from manifests, configuration, and explicit registration; ambiguity and unsupported frameworks reported | F01, F02 | [F01](F01.md): `discovery/test_frontend.py`; [F02](F02.md): `cli/test_component_target.py` | DONE |
| FR01.4 | Discovery separate from the core, dormant adapters, and fixtures; a shipped example activates nothing; active or modified helpers are checked | F01 | [F01](F01.md): `discovery/test_activation.py`, `engine/test_setup.py`, `ci/test_control.py` | DONE |
| FR01.5 | Existing configurations keep their meaning; no rewrite of user scripts or tsconfigs | F01 | [F01](F01.md): the existing policy and acceptance suites passed unchanged | DONE |

## FR02 Setup and startup

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| FR02.1 | Compatible pins incl. the browser revision; peer compatibility proven | F00, F02 | [Decision 0017](../../decisions/0017-browser-frontend-profile.md#versions); [F02](F02.md): `typescript/test_config.py`, `toolchain/test_committed_manifest.py` | DONE |
| FR02.2 | Vitest, jsdom, Testing Library, user-event; Playwright Test with Chromium | F02, F04, F05 | [F04](F04.md): Vitest, jsdom, Testing Library, and user-event in `acceptance/test_browser_units.py`; Playwright Test with Chromium: [F05](F05.md), `acceptance/test_browser_scenarios.py` | DONE |
| FR02.3 | Bootstrap and doctor provision and report the profile, browser, and Linux libraries during preparation only | F02 | [F02](F02.md): `typescript/test_chromium.py`, `typescript/test_provision.py`, `engine/test_setup.py`, a real bootstrap and doctor | DONE |
| FR02.4 | Missing Chromium fails a required browser gate; non-frontend projects need no browser | F02, F05 | [F02](F02.md): bootstrap and doctor fail without the browser, a Node component needs none; [F05](F05.md): the gate without the browser in `acceptance/test_browser_runs.py` | DONE |
| FR02.5 | Registration operation and a tested Quick start from a fresh template copy; the first CLI invocation | F02, F07 | [F07](F07.md): the README's Quick start run as written by `acceptance/test_frontend_start.py`; `./quality` is the first invocation | DONE |

## FR03 Static checks

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| FR03.1 | Prettier, typed ESLint, strict tsc, and structure over source, tests, and Node configuration; an empty solution tsconfig skips nothing | F03 | [F03](F03.md): `typescript/test_prettier.py`, `test_eslint.py`, `test_profile_browser.py`, helper tests, `acceptance/test_browser_static.py` | DONE |
| FR03.2 | A real type check separate from the bundler; a transpilable type error fails; aliases and references consistent | F03 | [F03](F03.md): `acceptance/test_browser_static.py` (`transpilable-type-error`), `test_typescript_layouts.py` | DONE |
| FR03.3 | React Hooks and selected JSX accessibility rules with explicit scopes | F03 | [F03](F03.md): helper `eslint-config.test.ts`, `typescript/test_eslint.py`, `test_browser.py`, the acceptance hook and accessibility cases | DONE |
| FR03.4 | Browser/server import boundaries through real resolution, incl. aliases and transitive dependencies | F03, F05 | [F03](F03.md): helper `imports.test.ts`, `typescript/test_boundaries.py`, the acceptance server-module and builtin cases; the build plugin: `typescript/test_build.py`, `acceptance/test_browser_build.py`; in the gate with the browser suites: [F05](F05.md), `typescript/test_endtoend.py` | DONE |
| FR03.5 | Base limits and counting unchanged; JSX depth is not nesting | F03 | [F03](F03.md): helper `nesting.test.ts` (JSX element depth is not control-flow nesting) | DONE |
| FR03.6 | CSS formatting and Stylelint; HTML entry points and production asset references; Sass and others unsupported | F03 | [F03](F03.md): `typescript/test_stylelint.py`, `test_entries.py`, `rules/test_style_suppressions.py`, the acceptance CSS and entry cases; built asset references: `typescript/test_bundle.py`, `acceptance/test_browser_build.py`; in the gate: [F05](F05.md), `typescript/test_endtoend.py` | DONE |
| FR03.7 | Precise classification of HTML, CSS, SVG, images, public files, bundles, and source maps; asset checks without coverage counters | F03 | [F03](F03.md): `discovery/test_browser_files.py`, `engine/test_measured.py` | DONE |

## FR04 Unit tests and coverage

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| FR04.1 | Meaningful logic, hook, and isolated component tests through observable interactions | F04, F05 | [F04](F04.md): a hook, conditional JSX, and an awaited interaction in `acceptance/test_browser_units.py` on a generated component; [F05](F05.md): the reference application's units at 100% | DONE |
| FR04.2 | Awaited interactions; unawaited user-event rejected by typed lint; conditional-JSX branch mapping | F03, F04 | [F03](F03.md): the unawaited-interaction acceptance case; [F04](F04.md): the case also fails its test, and `conditional-jsx-branches` | DONE |
| FR04.3 | Level by boundary; counted component tests run in the commit gate without services or network | F04 | [F04](F04.md): `acceptance/test_browser_units.py` (the unit suite in `quality check`, end-to-end suites out of it), `typescript/test_runner.py` and `process/test_isolation.py` (loopback only) | DONE |
| FR04.4 | 80/70/90 per frontend component; a new uncovered TS/TSX file fails | F04 | [F04](F04.md): `acceptance/test_browser_units.py` (each floor alone, `unimported-component`) | DONE |
| FR04.5 | Expected sources independent of imports; original files only; one owner; data combined, not averaged | F04 | [F04](F04.md): `unimported-component`, `conditional-jsx-branches` (TSX lines), `test_shared_source_is_covered_only_by_its_owner`; `rules/test_coverage.py` (counters added, never averaged) | DONE |
| FR04.6 | Result success, freshness, completeness, counters, and floors are a conjunction; end-to-end output never raises the unit numerator | F04, F05 | [F04](F04.md): `engine/test_suites.py`, `engine/test_suite_scope.py` (integration coverage never satisfies unit floors), `test-without-assertions`; [F05](F05.md): the Playwright suite returns no coverage report (`typescript/endtoend.py`), and `testing/test_playwright.py` reads its results | DONE |

## FR05 Snapshots, builds, and isolation

| ID | Requirement | Phases | Proof | Status |
| --- | --- | --- | --- | --- |
| FR05.1 | The complete candidate index; unstaged fixes do not rescue it; alternate index and concurrent-change protection kept | F04 | [F04](F04.md): `acceptance/test_browser_candidate.py`; `gitio/test_candidate.py` (concurrent index changes) | DONE |
| FR05.2 | Changes to CSS, assets, configuration, pins, or locks invalidate their scope | F04 | [F04](F04.md): `acceptance/test_browser_candidate.py` (a source, a test, the Vite configuration, a stylesheet, and an asset each run the unit suite); `acceptance/test_typescript.py` (a lockfile change) | DONE |
| FR05.3 | Isolated build with a declared environment; the exact fresh output is served; identity and digest in the evidence | F03, F05 | [F03](F03.md): `typescript/test_build.py`, `test_bundle.py`, `acceptance/test_browser_build.py` (identity and digest); [F05](F05.md): that output served by `typescript/test_serve.py`, kept in the gate's `build.json` | DONE |
| FR05.4 | No `.env.local`, stale `dist/`, ambient source, or inherited Git variables; only declared public values | F03, F05 | [F03](F03.md): `acceptance/test_browser_build.py` (`.env` files, a committed `dist/`, `GIT_DIR`, an ambient `VITE_*` value); [F05](F05.md): a stale `dist/` in the work tree is never served | DONE |
| FR05.5 | Caches distinct from results; built entry and assets usable; results checked independently | F03, F05 | [F03](F03.md): `typescript/test_bundle.py`, the missing-asset acceptance case; [F05](F05.md): the broken-asset and missing-response cases on the served output | DONE |
