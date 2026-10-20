"""Testing: normalized results, suite runs, static requests, and the JUnit parser."""

from quality.testing.junit import parse_junit
from quality.testing.model import (
    CaseResult,
    Outcome,
    StaticRequest,
    Suite,
    SuiteRequest,
    SuiteResults,
    SuiteRun,
    suite_roots,
)

__all__ = [
    "CaseResult",
    "Outcome",
    "StaticRequest",
    "Suite",
    "SuiteRequest",
    "SuiteResults",
    "SuiteRun",
    "parse_junit",
    "suite_roots",
]
