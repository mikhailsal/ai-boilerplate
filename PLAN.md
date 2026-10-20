# Implementation plan

This plan tracks the construction of the universal quality boilerplate. The
original assignment is external user input and is not part of the template.
Requirement IDs `R01`–`R10` and adversarial checks `A01`–`A16` come from that
assignment and are restated in the [traceability matrix](docs/plan/traceability.md).

## Status

- Current phase: P07
- Next action: complete the Dart profile
- Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`
- A box is checked only after the phase implementation commit exists and its
  checks were run; the phase record holds the SHA and evidence.

## Phases

| Done | Phase | Status | Record |
| --- | --- | --- | --- |
| [x] | P00 Inspect and establish the implementation contract | DONE | [P00](docs/plan/phases/P00.md) |
| [x] | P01 Build and test the minimal core | DONE | [P01](docs/plan/phases/P01.md) |
| [x] | P02 Implement discovery and candidate snapshots | DONE | [P02](docs/plan/phases/P02.md) |
| [x] | P03 Implement common policy and documentation gates | DONE | [P03](docs/plan/phases/P03.md) |
| [x] | P04 Implement the test and coverage engine | DONE | [P04](docs/plan/phases/P04.md) |
| [x] | P05 Complete Python and activate the strict hooks | DONE | [P05](docs/plan/phases/P05.md) |
| [x] | P06 Complete TypeScript | DONE | [P06](docs/plan/phases/P06.md) |
| [ ] | P07 Complete Dart | IN_PROGRESS | P07 |
| [ ] | P08 Complete PHP | TODO | P08 |
| [ ] | P09 Complete behavioral scenario enforcement | TODO | P09 |
| [ ] | P10 Implement portable CI and protection preparation | TODO | P10 |
| [ ] | P11 Prove template reuse and document maintenance | TODO | P11 |
| [ ] | P12 Final verification and handoff | TODO | P12 |

Hosted deployment status is tracked separately from implementation status in
the P10 and P12 records.

## Execution protocol

1. Read the phase prerequisites and acceptance criteria.
2. Implement a coherent change with meaningful tests and documentation.
3. Run the required checks, inspect results, and fix failures.
4. Create the implementation commit.
5. Mark the phase `[x]` and record the implementation SHA, checks, results,
   and limitations in the phase record.
6. Commit that progress update separately; it references the implementation
   commit, never its own SHA.

Until the repository gate existed (P00–P04), new code was validated with
pinned native commands. Since P05 every commit of this repository passes the
gate through the installed hooks. That construction order is not a shipped
bypass: no flag, environment variable, or permissive mode was added for it.

## Decisions

- [0001 Toolchain pins](docs/decisions/0001-toolchain-pins.md)
- [0002 Installation strategy](docs/decisions/0002-installation-strategy.md)
- [0003 Architecture and configuration layout](docs/decisions/0003-architecture.md)
- [0004 Candidate snapshots and revision semantics](docs/decisions/0004-candidate-snapshots.md)
- [0005 Coverage measurement paths](docs/decisions/0005-coverage-measurement.md)
- [0006 Discovery and classification](docs/decisions/0006-discovery-and-classification.md)
- [0007 Common gates](docs/decisions/0007-common-gates.md)
- [0008 Test and coverage engine](docs/decisions/0008-test-and-coverage-engine.md)
- [0009 Python profile](docs/decisions/0009-python-profile.md)
- [0010 Launcher, bootstrap, doctor, and hooks](docs/decisions/0010-launcher-bootstrap-and-hooks.md)

## Resumption

On resumption: inspect `git status` and `git log`, read this file and the last
phase record, verify that the recorded implementation SHA exists, and continue
from the first incomplete prerequisite.
