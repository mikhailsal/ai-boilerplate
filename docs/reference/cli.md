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
| `tools install` | Download, verify, and install the pinned standalone tools |

## Checking and testing

| Command | Purpose |
| --- | --- |
| `check [--staged \| --rev REV] [--all] [--json]` | Every gate over the affected components, or every active one with `--all`; the pre-commit hook runs `check --staged` |
| `test [--rev REV] [--suite S] [--component C] [--all] [--json]` | The declared suites; unit suites enforce the coverage floors |
| `self-test [--level unit\|acceptance] [--rev REV] [--json]` | The suites of the tooling components |
| `fix [--json]` | Safe native fixes and formatting in the working tree; nothing is staged |
| `links [--rev REV] [--timeout S] [--json]` | Probe external documentation links; not part of `check` |

## Inspection and policy

| Command | Purpose |
| --- | --- |
| `explain RULE \| --list` | What a rule checks and how to fix it |
| `inventory [--rev REV] [--json]` | How each candidate file is classified, with discovery findings |
| `policy validate` | Validate [`quality.toml`](../../quality.toml) |
| `policy schema` | Print, write, or check the generated [policy schema](policy.schema.json) |

## JSON reports

With `--json`, a command prints one JSON document with `schema_version`,
`command`, `exit_code`, a `summary` of error and warning counts, and the
`diagnostics`. Each finding carries its rule ID, severity, message, location,
component, and hint. `check`, `test`, and `self-test` add the tested
components and their coverage counters; `doctor` adds its check lines.

Commands planned for later phases: `gate` for merge CI (P10), and
`component add` and `tools update` (P11).
