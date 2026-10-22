# 0018 Browser builds, scenarios, and CI

Status: proposed (F00, 2026-10-22); the production build (F03), serving,
the browser scenarios, and accessibility (F05) are implemented, and the CI
job is not yet. It continues
[decision 0017](0017-browser-frontend-profile.md) with what a browser
component needs at the merge stage.

## Production build

The gate builds the candidate snapshot, never the work tree, with
`vite build` through a generated wrapper, as the Vitest wrapper of
[decision 0011](0011-typescript-profile.md#suites) does:

- the component's Vite configuration is loaded from the snapshot in
  production mode;
- `envDir` is an empty directory of the run, so no `.env`, `.env.local`, or
  `.env.production` file is read; the process environment is the sanitized
  one of the base, without `GIT_*` variables, plus only the declared public
  `VITE_*` values;
- the output goes to a new directory of the run with `emptyOutDir`, so a
  committed or stale `dist/` is never served;
- a boundary plugin records each Node builtin that Vite externalizes for
  the browser, unless the importer's package maps it in its `browser` field,
  each declared server-only module in the module graph, and each module of a
  declared server package imported from outside it; this covers transitive
  and aliased imports. The core reports them as `typescript.boundaries`,
  except imports by the browser sources, which the static check reports;
- Vite's manifest is written, and the evidence records the candidate's
  identity, every output file with its SHA-256, and their combined digest.

A failed build is a `typescript.build` finding. The output is validated as a
`typescript.build-output` finding: every declared entry point is built, and
every script, style, icon, and asset a built page references, and every
`url()` of the built CSS, is a file of the output below the resolved `base`
or a `data:` URL; a reference to another origin is reported too.

## Serving

The gate serves exactly that output with its own static server on
`127.0.0.1` and a port the kernel assigns, so an occupied port or another
application cannot answer for it. A directory without an index, or a path
without an extension, that names no file falls back to the first entry
point for client routing; any other missing file is a 404 and is recorded
before it is answered. The server stops when the suite ends, also on failure
or interruption. Playwright runs in a session of its own, whose remaining
processes are killed when it exits, and the gate never stops a process it
did not start.

## Browser scenarios

End-to-end suites of a browser component run Playwright Test through a
generated configuration that imports the component's own and then sets what
decides the verdict:

- `webServer` is removed and `baseURL` is the gate's server, so no
  development server and no reused server is tested;
- one project per declared viewport, all Chromium with the pinned
  executable, each test in a new browser context;
- `retries` 0, `forbidOnly`, an output directory of the run, and a gate
  reporter whose results the core parses;
- traces without screenshots or snapshots, kept outside the repository; the
  core reads console errors, page errors, and failed requests from them.

Case names are `file::title path[viewport]`, and a scenario selector of a
browser component must pass in every declared viewport. Skipped, focused
(`tests.focused`), expected-failure, flaky, empty, and stale results keep
their base meaning
([decision 0014](0014-behavioral-scenarios.md#what-runners-may-not-hide)).
A renderer crash fails the test at its next step that needs the page; a
crash after a test's last step goes unnoticed. A console or page error is a `typescript.browser-console` error, and a
same-origin request that the build cannot answer is a
`typescript.browser-resource` error; an exception names the rule, the test
file, and the exact message or path.

### Requirements

A browser component's `ui` capability requires, at the merge stage:

| Requirement | Proof |
| --- | --- |
| `ui.smoke` | The production build starts and renders its main interface |
| `ui.flows` | The declared critical user flows |
| `ui.accessibility` | Axe scans of the declared rendered states |
| `ui.keyboard` | Keyboard operation and focus handling of critical controls |

Only a browser component may declare `ui.accessibility` or `ui.keyboard`.
Each of its scenarios names its tested `boundary`, such as a browser network
route that simulates the backend; the check and the reports repeat it, and
it proves nothing about a real backend's contracts. A component that also
declares backend or database capabilities keeps their real-boundary tests.

## Accessibility

A test proves accessibility by asserting that the required interface is
present and then attaching the raw results of an `@axe-core/playwright`
scan named `accessibility-scan`. The gate checks each attachment: the axe
version is the locked one, the scan ran at least the tags of the
component's `accessibility_tags` (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`
by default) and turned off no rule, and it checked a page of the gate's
server that had content; otherwise it is a `typescript.accessibility-scan`
error. Serious and critical violations are `typescript.accessibility`
errors, moderate and minor ones warnings, and incomplete results are
reported for manual review. An exception names the axe rule, the test file,
and the target. A scenario of `ui.accessibility` whose test lacks a valid
scan in any viewport fails with `scenarios.evidence`. Scans are evidence for
the selected rules, not a conformance claim.

Visual, bundle-size, and performance budgets are not part of this baseline;
they would be enhanced capabilities with their own measurement and blocking
rules.

## Stages and CI

- Commit stage: the common gates, the static checks, the type check, and the
  unit suites with the floors, over the candidate index.
- Merge stage: all of that again, plus the build, the Chromium scenarios,
  accessibility, the dependency audit, and the history checks.
- `quality gate --stage merge` runs the whole path on any Linux machine.

The workflow gets a `browser` job, and the aggregate requires it with `gate`
and `audit`. The CLI, not the workflow, decides whether the candidate
affects a browser component; the job always runs, installs the browser's
system libraries only when the CLI says so, and passes with nothing to do
otherwise, so a skipped or missing job still fails the aggregate. The GitLab
wrapper mirrors it. Hosting settings are prepared, not applied.

## Alternatives rejected

- `vite preview` or Playwright's `webServer`: their ports, reuse, and proxy
  follow the project's configuration.
- Parsing Playwright's console output: traces and a reporter give structured
  results.
- A fixed sleep before the first navigation: readiness is the server's bound
  socket, and Playwright waits for conditions.
