"""Testing: normalized results, suite runs, static requests, and the results parsers."""

from quality.testing.dartjson import parse_dart_json
from quality.testing.junit import parse_junit
from quality.testing.model import (
    CaseResult,
    Outcome,
    ResultsFormat,
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
    "ResultsFormat",
    "StaticRequest",
    "Suite",
    "SuiteRequest",
    "SuiteResults",
    "SuiteRun",
    "parse_dart_json",
    "parse_junit",
    "suite_roots",
]
