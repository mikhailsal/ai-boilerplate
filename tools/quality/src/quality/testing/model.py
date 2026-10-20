"""Normalized test results, the records of one suite run, and the static gates' request.

Both requests live here, below the adapters, because the engine builds them and
every profile adapter receives them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from quality.policy import Component


class Suite(StrEnum):
    """A declared test suite; only unit suites feed the coverage thresholds."""

    UNIT = "unit"
    INTEGRATION = "integration"
    CONTRACT = "contract"
    E2E = "e2e"
    ACCEPTANCE = "acceptance"


class Outcome(StrEnum):
    """The result of one test case."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class CaseResult:
    """One executed or skipped test case."""

    name: str
    outcome: Outcome


@dataclass(frozen=True, slots=True)
class SuiteResults:
    """The test cases of one suite run."""

    cases: tuple[CaseResult, ...]

    def count(self, *outcomes: Outcome) -> int:
        """Count the cases with any of the outcomes."""
        return sum(1 for case in self.cases if case.outcome in outcomes)

    @property
    def executed(self) -> int:
        """Cases that ran, whatever their result."""
        return len(self.cases) - self.count(Outcome.SKIPPED)

    @property
    def failing(self) -> int:
        """Cases that failed or raised an error."""
        return self.count(Outcome.FAILED, Outcome.ERROR)


@dataclass(frozen=True, slots=True)
class SuiteRequest:
    """One suite to run: the component, its test roots, and a new empty output directory.

    `started` is the time the output directory was created; reports must not be older.
    `work` is the snapshot's private work area, where runners keep environments.
    """

    component: Component
    suite: Suite
    roots: tuple[str, ...]
    snapshot: Path
    output: Path
    started: float
    work: Path

    @property
    def directory(self) -> Path:
        """The component root inside the snapshot, where native tools run."""
        return self.snapshot / self.component.root


@dataclass(frozen=True, slots=True)
class StaticRequest:
    """The files of one prepared component that its static gates check, in a snapshot.

    `files` are the component's source and test files; `configs` are its
    configuration files written in a programming language, such as
    `eslint.config.js`, which formatters check too. Paths are repository paths.
    """

    component: Component
    snapshot: Path
    work: Path
    files: tuple[str, ...]
    configs: tuple[str, ...] = ()

    @property
    def directory(self) -> Path:
        """The component root inside the snapshot, where native tools run."""
        return self.snapshot / self.component.root


@dataclass(frozen=True, slots=True)
class SuiteRun:
    """What a runner reports back: its exit status and the reports it wrote."""

    returncode: int
    results: Path
    coverage: Path | None = None


def suite_roots(component: Component, suite: Suite) -> tuple[str, ...]:
    """Return the test roots a component declares for a suite, relative to its root."""
    tests = component.tests
    roots = {
        Suite.UNIT: tests.unit,
        Suite.INTEGRATION: tests.integration,
        Suite.CONTRACT: tests.contract,
        Suite.E2E: tests.e2e,
        Suite.ACCEPTANCE: tests.acceptance,
    }
    return tuple(roots[suite])
