# Implementation plan

This plan tracks the construction of the universal quality boilerplate. The
original assignment is external user input and is not part of the template.
Requirement IDs `R01`–`R10` and adversarial checks `A01`–`A16` come from that
assignment and are restated in the [traceability matrix](docs/plan/traceability.md).

## Status

- Current phase: P03
- Next action: implement common file, documentation, secret, and exception gates
- Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`
- A box is checked only after the phase implementation commit exists and its
  checks were run; the phase record holds the SHA and evidence.

## Phases

| Done | Phase | Status | Record |
| --- | --- | --- | --- |
| [x] | P00 Inspect and establish the implementation contract | DONE | [P00](docs/plan/phases/P00.md) |
| [x] | P01 Build and test the minimal core | DONE | [P01](docs/plan/phases/P01.md) |
| [x] | P02 Implement discovery and candidate snapshots | DONE | [P02](docs/plan/phases/P02.md) |
| [ ] | P03 Implement common policy and documentation gates | IN_PROGRESS | P03 |
| [ ] | P04 Implement the test and coverage engine | TODO | P04 |
| [ ] | P05 Complete Python and activate the strict hooks | TODO | P05 |
| [ ] | P06 Complete TypeScript | TODO | P06 |
| [ ] | P07 Complete Dart | TODO | P07 |
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

Until the repository gate exists (P05), new code is validated with pinned
native commands. That construction order is not a shipped bypass: no flag,
environment variable, or permissive mode is added for it.

## Decisions

- [0001 Toolchain pins](docs/decisions/0001-toolchain-pins.md)
- [0002 Installation strategy](docs/decisions/0002-installation-strategy.md)
- [0003 Architecture and configuration layout](docs/decisions/0003-architecture.md)
- [0004 Candidate snapshots and revision semantics](docs/decisions/0004-candidate-snapshots.md)
- [0005 Coverage measurement paths](docs/decisions/0005-coverage-measurement.md)
- [0006 Discovery and classification](docs/decisions/0006-discovery-and-classification.md)

## Resumption

On resumption: inspect `git status` and `git log`, read this file and the last
phase record, verify that the recorded implementation SHA exists, and continue
from the first incomplete prerequisite.
