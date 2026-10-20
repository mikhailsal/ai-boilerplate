"""Testing: normalized results, suite runs, and the JUnit parser (no subprocesses)."""

from quality.testing.junit import parse_junit
from quality.testing.model import (
    CaseResult,
    Outcome,
    Suite,
    SuiteRequest,
    SuiteResults,
    SuiteRun,
    suite_roots,
)

__all__ = [
    "CaseResult",
    "Outcome",
    "Suite",
    "SuiteRequest",
    "SuiteResults",
    "SuiteRun",
    "parse_junit",
    "suite_roots",
]
