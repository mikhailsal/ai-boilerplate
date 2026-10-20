# 0005 Coverage measurement paths

Status: accepted (P00). Each path below was exercised on 2026-10-20 with the
pinned versions in a scratch project (spikes are not tracked; their findings
are summarized here and become acceptance tests in P05–P08).

## Common model

Every adapter produces, per source file: executable lines with hit counts and
branch opportunities with hit flags, in the native tool's own semantics. The
core keeps line and branch counters separate, compares exact integers, and
never merges languages. An expected source inventory is computed from the
candidate tree and reconciled with the report; a missing file is an error.

## Python: coverage.py 7.16.2

- Run: `python -m pytest --cov=<source roots> --cov-branch
  --cov-report=json:<fresh path> --junitxml=<fresh path>`.
- Report: JSON format 3. Per file `executed_lines`, `missing_lines`,
  `executed_branches`, `missing_branches` (arcs).
- Unimported files under `--cov` source roots are reported with zero hits
  (verified).
- Native semantics: a branch is a possible jump between lines (an arc).
  Boolean short-circuit operands and conditional expressions on one line are
  not separate branches.

## TypeScript: Vitest 5.0.5 with V8 provider

- Run: `vitest run --coverage --coverage.reporter=lcovonly
  --coverage.reporter=json` with `coverage.include` listing the component's
  source globs for `.ts`, `.tsx`, `.mts`, `.cts`, and the JUnit reporter.
- Report: LCOV (`DA`, `BRDA`, `BRF`, `BRH`) remapped to original sources;
  emitted JavaScript is not counted because only source globs are included.
- Unimported files appear with zero hits only through `coverage.include`
  (Vitest 5 has no `all` option). Type-only files report zero lines and are
  `NOT_APPLICABLE`.
- Vite 8 does not transform `.cts` by default; the profile sets
  `oxc.include` to cover `.cts`. Aliases use `resolve.tsconfigPaths`.
- Native semantics: Istanbul branch types `if`, `cond-expr`, `binary-expr`
  (`&&`, `||`, `??`), `switch`, `default-arg`.
- Zero test files exit 1; the adapter treats it as `tests.none`.

## Dart: `dart test --coverage-path --branch-coverage` (SDK 3.13.6)

- Run per package: `dart test --branch-coverage --coverage-path=<fresh lcov>
  --coverage-package='^<name>$' --file-reporter json:<fresh path>`.
- Report: LCOV with `DA` and `BRDA` but no `BRF`/`BRH`; the parser derives
  totals from the `BRDA` records.
- Unimported libraries do not appear. The adapter generates, inside the
  snapshot only, a test that imports every non-`part` library under `lib/`, so
  the VM force-compiles them and reports zero hits (verified).
- Native semantics: a branch is a VM basic-block entry (then/else blocks,
  switch cases, loop bodies, catch blocks) aggregated per line. `&&`, `??`,
  and conditional expressions are not instrumented; an `if` without `else`
  has no implicit-else opportunity. This limitation is declared, not hidden.
- Coverage needs a loopback VM service (ephemeral `127.0.0.1` ports); this is
  the permitted instrumentation IPC.
- Zero tests exit 79; a missing `test/` exits 65; both are errors.
- Flutter is detected from `flutter: {sdk: flutter}` dependencies, an
  `environment.flutter` constraint, or a top-level `flutter:` section and is
  reported as an unsupported variant.

## PHP: PHPUnit 13.4.3 with Xdebug 3.5

- Run: `php -d zend_extension=xdebug -d xdebug.mode=coverage` with
  `XDEBUG_MODE=coverage`, `phpunit --coverage-clover <fresh path>
  --log-junit <fresh path> --log-otr <fresh path>` and `branchCoverage="true"`.
- Report: Clover gives per-file `conditionals`/`coveredconditionals` and
  per-line statement counts; Cobertura and `--coverage-xml` do not preserve
  per-file branch counts, so they are not used.
- Uncovered files are included for lines, but files never loaded during a
  test have no branch data. The adapter generates, inside the snapshot, a test
  that loads every source file while coverage is active, so their branch
  opportunities are counted.
- A missing driver, PCOV, or Xdebug without coverage mode makes PHPUnit abort
  without a report; the adapter treats any missing report as an error.
  A Clover report with branch coverage disabled shows `conditionals="0"`,
  which is never accepted as measured when the file has branch opportunities.
- Native semantics: a branch is an Xdebug branch (opcode-level jump target).
- Skipped and incomplete tests are distinguished with the Open Test Reporting
  (`--log-otr`) output.

## Evidence rules

Each run gets a new empty output directory; reports must exist after the
runner exits, must be parseable, must reference only snapshot files, and are
discarded if the runner failed. Zero executed tests in a declared unit suite
fail. Integration and end-to-end runs never feed unit thresholds.
