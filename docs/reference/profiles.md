# Profile support matrix

A component's `profile` in [`quality.toml`](../../quality.toml) selects the
native tools that check it. `./quality component add` detects the profile
from the manifest at the component root. The pinned versions are in
[`toolchains.toml`](../../tools/quality/toolchains.toml) and
[decision 0001](../decisions/0001-toolchain-pins.md).

## Tier 1 profiles

| | Python | TypeScript | Dart | PHP |
| --- | --- | --- | --- | --- |
| Decision | [0009](../decisions/0009-python-profile.md) | [0011](../decisions/0011-typescript-profile.md) | [0012](../decisions/0012-dart-profile.md) | [0013](../decisions/0013-php-profile.md) |
| Manifest | `pyproject.toml` | `package.json` | `pubspec.yaml` | `composer.json` |
| Lockfile | `uv.lock` | `package-lock.json`, or a workspace root's | `pubspec.lock`, or a pub workspace root's | `composer.lock` |
| Sources (`component add` default) | `src` | `src` | `lib`, and `bin` when present | `src` |
| Unit tests (default) | `tests` | `tests` | `test` | `tests` |
| Formatting | Ruff | Prettier | `dart format` | PHP CS Fixer, `@PER-CS` |
| Lint | Ruff | ESLint with typescript-eslint | `dart analyze` with package:lints | PHPStan |
| Types | Pyright, strict | `tsc` | `dart analyze`, strict modes | PHPStan, level max |
| Tests | pytest | Vitest | package:test | PHPUnit |
| Coverage report | coverage.py JSON | LCOV from V8 | LCOV from package:coverage | Clover and JSONL from php-code-coverage |
| Branch coverage | Yes | Yes | Yes | Yes, with Xdebug |
| Structure and imports | Core, from the Python AST | Node helper | Dart helper | PHP helper |
| Installed by bootstrap | uv environment of the component | Node and the locked npm packages | Dart SDK and the locked pub packages | Composer and the locked packages |
| System requirement | None | None | None | PHP and Xdebug at the minor versions in `[runtimes]` |

The tools the core itself needs (uv, CPython, gitleaks, actionlint, and
osv-scanner) are installed for every repository. A profile's toolchain is
installed only when a component uses that profile, or when a candidate
changes the profile's helper bundle in `tools/quality/helpers`. The
prerequisites are in [decision 0002](../decisions/0002-installation-strategy.md).

## Unsupported source

Source files are classified by extension and owner
([decision 0006](../decisions/0006-discovery-and-classification.md)). A
source file of another language inside a component fails with
`discovery.language-mismatch`, and a source language that no profile
supports, such as Go or Ruby, fails with `discovery.unsupported-language`.
Neither passes silently, and both name the file. Unsupported variants of a
supported language also fail: Flutter and web Dart packages, and JavaScript
sources in a TypeScript component.

The browser target of the TypeScript profile, `target = "browser"`
([decision 0017](../decisions/0017-browser-frontend-profile.md)), is not
supported by this build yet: a component that declares it fails every check,
bootstrap, and doctor with `typescript.browser-incomplete`, which cannot be
excepted. Bootstrap already installs the pinned Chromium for an active
browser component, and bootstrap and doctor report whether it starts and
matches the locked Playwright.

## Several components

A repository may hold any mix of profiles, and several components of the
same profile. Each component has its own root, manifest, and lockfile, and
the thresholds of the shared policy; no two components may share a root or
overlapping source and test directories. Coverage floors and scenario
manifests apply per component.

## Adding a profile

A new language or coverage format is a change to the core, described in the
[extension guide](../guides/extending.md). The profile contract tests in
`tools/quality/tests/unit/test_profile_contract.py` fail until every stage
knows the new profile.
