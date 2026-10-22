# 0017 Browser frontend profile

Status: proposed (F00, 2026-10-22). The phases of the frontend extension
implement it; until a section says it is implemented, a component that needs
it fails with an explicit finding instead of passing.

## Scope

The TypeScript profile ([decision 0011](0011-typescript-profile.md)) gains a
second execution target: single-page **React + Vite + TypeScript** browser
applications on Linux (x86_64 and aarch64, glibc), built to static production
output. The baseline test stack is fixed:

- unit and integration suites: Vitest with jsdom, React Testing Library, and
  user-event, with V8 coverage remapped to the original TS/TSX;
- end-to-end suites: Playwright Test with a pinned Chromium headless shell
  against the production build, and `@axe-core/playwright` scans.

Not supported, and reported as such instead of being checked loosely: other
frameworks (Vue, Svelte, Solid, Preact, Angular), server-side rendering,
React Server Components, Next.js and other meta-frameworks, React Native,
bundlers other than Vite, Sass, Less, and Stylus, Vitest Browser Mode, and
browsers other than Chromium. Each needs its own advertised and tested
capability before it is accepted.

## Component model

- `profile = "typescript"` stays the language profile. A new component field
  `target` is `"node"` (the default) or `"browser"`, so every existing
  configuration keeps its meaning and no migration is needed.
- `target = "browser"` requires `framework = "react"`, `bundler = "vite"`,
  and the `ui` capability. `framework` and `bundler` are invalid without it,
  and `target` is invalid for the Python, Dart, and PHP profiles.
- An optional `[components.browser]` table holds what only a browser
  component has: its HTML entry points (default `index.html`), the declared
  public build-time values (`VITE_*` names with non-secret values), the
  server-only modules and packages its browser code must not import, and the
  viewports of its browser scenarios.
- React rules, DOM globals, the jsdom environment, the build, and the browser
  are applied only to components whose target is `browser`. A Node component
  of the same repository keeps the base checks.
- Ownership is unchanged: the longest root owns a file, and shared source has
  exactly one owner.

### Activation

A shipped reference application has the new role `example`. It is checked
in maintainer mode and when the candidate changes it, and never because an
application uses its profile or target, so an exported Node-only project
gets no browser requirement from it. Helpers keep their rule
([decision 0003](0003-architecture.md)); the browser tools are set up only
for an active component whose target is `browser`.

### Registration

`quality component add <directory> --target browser` registers a React/Vite
application. It is recognized only from its manifests and configuration:
`package.json` declares `react`, `react-dom`, `vite`, and
`@vitejs/plugin-react`, and the directory has a `vite.config.*` and the
HTML entry point. A `.tsx` file or `package.json` alone proves nothing.
Without `--target`, a directory with that evidence is ambiguous and is
reported, and packages of an unsupported framework make the registration
fail. The command never edits the project's scripts or tsconfigs.

## Versions

Read from the npm registry on 2026-10-22 with the pinned Node.js; each was
installed together with `npm install --strict-peer-deps`, which accepted the
set, and a probe application built, linted, type-checked, and ran its unit
and Chromium tests with them.

| Package | Version | Compatibility evidence |
| --- | --- | --- |
| react, react-dom | 19.3.1 | Peer of React Testing Library `^18 \|\| ^19` |
| @types/react, @types/react-dom | 19.3.0 | Matching type packages |
| vite | 8.3.5 | Vitest 5.0.5 accepts `^6.4 \|\| ^7 \|\| ^8`; Node `>=22.12` |
| @vitejs/plugin-react | 6.1.2 | Requires Vite `^8` |
| jsdom | 30.1.3 | Vitest peer `*` |
| @testing-library/react, dom, user-event | 16.3.3, 10.4.2, 14.6.8 | Peers satisfied |
| eslint-plugin-react-hooks | 7.1.1 | ESLint `^3`–`^10` |
| eslint-plugin-jsx-a11y-x | 0.2.0 | ESLint `^9 \|\| ^10` |
| globals | 17.13.0 | Browser and Node global sets for ESLint |
| stylelint | 17.16.0 | Node `>=20.19` |
| stylelint-config-standard, stylelint-config-css-modules | 40.0.0, 4.6.0 | Stylelint `^17` |
| @playwright/test | 1.64.1 | Expects Chromium headless shell revision 1248 |
| @axe-core/playwright | 4.14.0 | Locks axe-core 4.14.0 |
| Chrome headless shell | 156.0.8078.4 | Revision 1248 in Playwright's `browsers.json` |

The existing pins stay: TypeScript 6.0.3, ESLint 10.13.0, typescript-eslint
8.72.0, Prettier 3.9.10, and Vitest with `@vitest/coverage-v8` 5.0.5.

`eslint-plugin-jsx-a11y` 6.10.2, the latest release, declares ESLint up to
`^9`, and `npm install` refuses it beside ESLint 10.13.0 (`ERESOLVE`).
Overriding the peer range or `--legacy-peer-deps` would ignore that failure,
and dropping the rule family would hide it. The maintained fork
`eslint-plugin-jsx-a11y-x` 0.2.0 declares ESLint 10 and ships the same 36
rules under the `jsx-a11y-x/` prefix; the probe reported `alt-text`,
`click-events-have-key-events`, and `no-static-element-interactions` from
it. The upstream plugin replaces it once a release accepts ESLint 10.

### Chromium

The browser is a pinned tool in `tools/quality/toolchains.toml`, installed
by `quality bootstrap` into the quality cache, never into Playwright's own
cache. Playwright 1.64.1 downloads the Chrome for Testing headless shell
156.0.8078.4 from Google's `chrome-for-testing-public` bucket and verifies no
checksum; Google publishes no SHA-256 for it. Both archives were downloaded
and matched the MD5 digests the bucket publishes (`x-goog-hash`); their
SHA-256 values are pinned:

| Archive | Size | SHA-256 |
| --- | --- | --- |
| `linux64/chrome-headless-shell-linux64.zip` | 125797539 | `c3e50596aef52c58f8fda3c6b3411c33d34c88b177b3ed1c2243359fd3b8ba20` |
| `linux-arm64/chrome-headless-shell-linux-arm64.zip` | 125711061 | `81ab9d4d3c301dc5fdfb6c541b9e6632b16fc819a6a854460f40a76fe2b2c476` |

Without a vendor checksum file the tool names no `checksums`, so
`quality tools update` refuses it and an update is a reviewed edit with the
same proof. The gate compares the pinned version with the
`chromium-headless-shell` entry of the `browsers.json` of the component's
locked `playwright-core` and fails on a mismatch.

## Static checks

- Prettier formats TS/TSX, CSS, and the HTML entry points; typed ESLint
  runs as for Node components.
- The helper verifies that every browser source file has
  `react-hooks/rules-of-hooks`, `react-hooks/exhaustive-deps`, and the
  selected `jsx-a11y-x` rules enabled, and every test file
  `@typescript-eslint/no-floating-promises`, which rejects an unawaited
  user-event call.
- `tsc` runs through the helper over the solution `tsconfig.json` and its
  references, so an empty solution file cannot skip the app or test
  projects; a type error that Vite would still transpile fails.
- The base structure limits apply unchanged. JSX element depth is not
  control-flow nesting, and render functions are measured like any other.
- Import boundaries: browser source files may not import Node builtins or the
  declared server-only modules and packages, resolved through the
  component's tsconfig paths; the build adds the transitive check.
  Configuration files such as `vite.config.ts` keep their Node environment.
- Stylelint with the standard and CSS Modules configurations checks authored
  CSS; a `stylelint-disable` comment is an inline suppression like any other.
  A Sass, Less, or Stylus file is an unsupported variant.
- Declared HTML entry points must exist, and their scripts, styles, and
  icons must resolve to files of the candidate.
- CSS, HTML, SVG, images, and `public/` files are assets: they keep the blob,
  secret, and path checks and get no coverage counters. Source maps and build
  output are generated files.

## Unit tests and coverage

Browser unit and integration suites run Vitest with the jsdom environment
and `expect.requireAssertions`, through the generated wrapper of decision
0011. The expected sources are every TS/TSX file of the source roots except
`.d.ts` files, imported or not, so an untested entry point fails. Coverage
is the V8 data remapped to the original files, with the base floors of
`quality.toml` per component; end-to-end suites measure no coverage, so they
cannot raise the unit numerator.

The production build, the browser scenarios, accessibility, and CI are in
[decision 0018](0018-browser-builds-and-scenarios.md).

## Alternatives rejected

- Upstream `eslint-plugin-jsx-a11y` with a peer override: accepts a declared
  incompatibility.
- Playwright's `playwright install`: verifies nothing and writes to a shared
  user cache outside the pins.
- Vitest Browser Mode as the baseline: it would change the unit-suite and
  coverage contract; it remains a possible optional profile.
- A frontend runner beside the engine: the profile, scenario registry, and
  CLI of the base are extended instead.
