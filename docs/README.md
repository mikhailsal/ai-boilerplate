# Documentation index

## Decisions

| Decision | Topic |
| --- | --- |
| [0001](decisions/0001-toolchain-pins.md) | Toolchain pins and versions |
| [0002](decisions/0002-installation-strategy.md) | Installation strategy and prerequisites |
| [0003](decisions/0003-architecture.md) | Architecture and configuration layout |
| [0004](decisions/0004-candidate-snapshots.md) | Candidate snapshots and revision semantics |
| [0005](decisions/0005-coverage-measurement.md) | Coverage measurement |
| [0006](decisions/0006-discovery-and-classification.md) | Discovery and classification |
| [0007](decisions/0007-common-gates.md) | Common repository, documentation, and structure gates |
| [0008](decisions/0008-test-and-coverage-engine.md) | Test and coverage engine |
| [0009](decisions/0009-python-profile.md) | Python profile: Ruff, Pyright, pytest, coverage.py |
| [0010](decisions/0010-launcher-bootstrap-and-hooks.md) | Launcher, bootstrap, doctor, and managed hooks |

## Reference

- [Command-line reference](reference/cli.md): commands, options, exit codes,
  and JSON reports.
- [Policy JSON Schema](reference/policy.schema.json), generated from the
  policy models; the policy itself is [`quality.toml`](../quality.toml).
- [Quality core](../tools/quality/README.md): layout, exit codes, and native
  development commands.
- [Agent instructions](../AGENTS.md): setup and the everyday commands.

## Plan

- [Implementation plan](../PLAN.md) with one record per phase.
- [Requirement traceability](plan/traceability.md) and the
  [adversarial checklist](plan/adversarial.md).
