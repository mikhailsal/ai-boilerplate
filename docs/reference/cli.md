# Command-line reference

Run every command from the repository root as `./quality <command>`.
`./quality <command> --help` prints the full option list. Commands that judge
a candidate read the index by default, or a commit with `--rev`, from an
isolated snapshot ([decision 0004](../decisions/0004-candidate-snapshots.md)).
`check`, `test`, and `self-test` are judged by the candidate's own core: when
the working-tree core differs, the candidate's core runs the command as a
child process, and a candidate core lockfile that differs from the installed
environment fails with `core.environment`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Passed |
| 1 | Violations found |
| 2 | Usage or policy error |
| 3 | Environment or tool error |
| 4 | Internal error |

## Setup and environment

| Command | Purpose |
| --- | --- |
| `bootstrap [--pre-push]` | Install the pinned tools, interpreters, and locked packages, then the managed hooks ([decision 0010](../decisions/0010-launcher-bootstrap-and-hooks.md)) |
| `doctor [--json]` | Verify offline and read-only that checks can run here |
| `tools install [NAME ...]` | Download, verify, and install pinned tools from `tools/quality/toolchains.toml`: gitleaks by default, or the named ones such as `node`, `dart`, or `composer`; bootstrap installs Node only for a TypeScript component, the Dart SDK only for a Dart component, and Composer only for a PHP component |

## Checking and testing

| Command | Purpose |
| --- | --- |
| `check [--staged \| --rev REV] [--all] [--stage commit\|merge] [--json]` | Every gate over the affected components, or every active one with `--all`, and the suites that prove the scenarios mandatory at the stage ([decision 0014](../decisions/0014-behavioral-scenarios.md)); the pre-commit hook runs `check --staged` at the commit stage |
| `test [--rev REV] [--suite S] [--component C] [--all] [--json]` | The declared suites, and the scenarios they prove; unit suites enforce the coverage floors |
| `self-test [--level unit\|e2e\|acceptance] [--rev REV] [--json]` | The suites of the tooling components; `e2e` runs the built-artifact suites |
| `fix [--json]` | Safe native fixes and formatting in the working tree; nothing is staged |
| `links [--rev REV] [--timeout S] [--json]` | Probe external documentation links; not part of `check` |

## Inspection and policy

| Command | Purpose |
| --- | --- |
| `explain RULE \| --list` | What a rule checks and how to fix it |
| `inventory [--rev REV] [--json]` | How each candidate file is classified, with discovery findings |
| `policy validate` | Validate [`quality.toml`](../../quality.toml) |
| `policy schema [--scenarios] [--write \| --check]` | Print the generated [policy schema](policy.schema.json), or the [scenario manifest schema](scenarios.schema.json) with `--scenarios`; write or check both |
| `scenarios [--rev REV] [--json]` | Validate the scenario manifests without running tests, list their scenarios, and suggest undeclared capabilities |

## JSON reports

With `--json`, a command prints one JSON document with `schema_version`,
`command`, `exit_code`, a `summary` of error and warning counts, and the
`diagnostics`. Each finding carries its rule ID, severity, message, location,
component, and hint. `check`, `test`, and `self-test` add the tested
components, their coverage counters, and per component the scenarios required,
proved, suspended, and not required by the run; `scenarios` adds every
scenario of the manifests; `doctor` adds its check lines.

Commands planned for later phases: `gate` for merge CI (P10), and
`component add` and `tools update` (P11).
