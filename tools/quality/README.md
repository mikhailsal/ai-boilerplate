# Quality core

The `quality` command-line tool decides whether a candidate change passes.
Git hooks and CI only call it. This directory holds its typed Python source,
unit and acceptance tests, the stdlib launcher, and locked development tooling.

## Layout

| Path | Contents |
| --- | --- |
| `src/quality/diagnostics` | Finding model, rule registry, text and JSON renderers |
| `src/quality/process` | Subprocess runner and allowlisted child environments |
| `src/quality/policy` | `quality.toml` models, loading, cross-validation, schema export |
| `src/quality/gitio` | Candidate trees, isolated snapshots, and changed-line diffs from Git plumbing |
| `src/quality/discovery` | File types, manifests, classification, ownership, activation, test scope |
| `src/quality/metrics` | Structure metrics model shared by profile adapters |
| `src/quality/boundedio.py` | Bounded JSON and XML readers for native tool reports |
| `src/quality/testing` | Suite and result model, JUnit XML parser |
| `src/quality/coverage` | Coverage model and parsers for coverage.py JSON, LCOV, and Clover |
| `src/quality/adapters` | Native tool adapters: the Python profile (Ruff, Pyright, pytest, uv environments, fixes), the TypeScript profile (Prettier, ESLint, tsc, Vitest, npm environments, fixes), Python structure and imports, Markdown lint, gitleaks, HTTP probes |
| `src/quality/rules` | Common rules: files, configuration, suppressions, docs, links, structure, architecture, exceptions, tests, coverage |
| `src/quality/toolchain` | Pinned standalone tool manifest and verified installation |
| `src/quality/hooks` | Text, installation, and status of the managed Git hooks |
| `src/quality/engine` | Orchestration of `check`, history ranges, external links, test suites, fixes, bootstrap, and doctor |
| `src/quality/catalog.py` | The registry of every rule the core can report |
| `src/quality/cli` | Argument parsing and subcommands (`bootstrap`, `check`, `doctor`, `explain`, `fix`, `inventory`, `links`, `policy`, `self-test`, `test`, `tools`) |
| `src/quality/testkit` | Test builders shared by unit, contract, and acceptance tests, including scratch projects with real hooks |
| `toolchains.toml` | Versions, URLs, and SHA-256 checksums of standalone tools and Node, and the npm packages TypeScript components lock |
| `helpers/typescript` | The Node helper of the TypeScript profile: types, structure, imports, and ESLint configuration probes; a separate component |
| `tests/unit` | Unit tests; they must keep core coverage at the policy minimum |
| `tests/acceptance` | Acceptance tests: real commits and pushes through the managed hooks in scratch repositories |
| `launcher/` | The `./quality` launcher, a separate component that runs on the system `python3` |

Packages depend only on lower layers, as described in
[decision 0003](../../docs/decisions/0003-architecture.md); the layer order is
declared in the root `quality.toml` and enforced by `quality check`. The gates
themselves are described in
[decision 0007](../../docs/decisions/0007-common-gates.md), and the test and
coverage engine in
[decision 0008](../../docs/decisions/0008-test-and-coverage-engine.md). The Python profile is
[decision 0009](../../docs/decisions/0009-python-profile.md), the TypeScript profile
[decision 0011](../../docs/decisions/0011-typescript-profile.md), and the launcher,
bootstrap, doctor, and hooks are
[decision 0010](../../docs/decisions/0010-launcher-bootstrap-and-hooks.md).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Passed |
| 1 | Violations found |
| 2 | Usage or policy error |
| 3 | Environment or tool error |
| 4 | Internal error |

## Native development commands

Day to day, use the gate itself from the repository root:
`./quality self-test` (unit suites with coverage) and
`./quality self-test --level acceptance`. The tool versions are locked in
`pyproject.toml` and `uv.lock`
([decision 0001](../../docs/decisions/0001-toolchain-pins.md)); after
`./quality bootstrap`, the native commands run from this directory:

```sh
.venv/bin/ruff format --check src tests
.venv/bin/ruff check src tests
.venv/bin/pyright
PYTHONPATH=src .venv/bin/python -m pytest tests/unit --cov=src --cov-branch
PYTHONPATH=src .venv/bin/python -m pytest tests/acceptance
```

The TypeScript helper runs on the pinned Node. `./quality bootstrap` caches
the packages of its `package-lock.json`, and `npm ci --offline` installs them
into `node_modules`. The native commands run from `helpers/typescript` with
that Node first on `PATH` (`~/.cache/quality/toolchains/node-24.22.0/bin` by
default):

```sh
npm ci --offline --ignore-scripts
node_modules/.bin/prettier --check src tests eslint.config.js vitest.config.ts
node_modules/.bin/eslint src tests
node_modules/.bin/tsc -p .
node_modules/.bin/vitest run --coverage --coverage.include=src --coverage.reporter=text-summary
```

After changing a policy model, regenerate the committed schema from the
repository root:

```sh
./quality policy schema --write
```
