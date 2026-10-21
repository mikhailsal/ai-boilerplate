"""One suite run and its evidence: fresh reports from a new output directory (R06)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from quality.adapters.native import ToolFailedError
from quality.boundedio import ReportError, read_bounded
from quality.diagnostics import Diagnostic, Severity
from quality.engine.profiles import ProfileTests
from quality.policy import Policy
from quality.rules import coverage, testing
from quality.testing import (
    ResultsFormat,
    Suite,
    SuiteRequest,
    SuiteResults,
    SuiteRun,
    parse_dart_json,
    parse_junit,
)

# File systems with coarse timestamps may date a new report up to this many seconds early.
FRESHNESS_SLACK = 2.0
PARSERS: dict[ResultsFormat, Callable[[bytes, str], SuiteResults]] = {
    ResultsFormat.JUNIT: parse_junit,
    ResultsFormat.DART_JSON: parse_dart_json,
}


def read_evidence(path: Path, request: SuiteRequest) -> bytes:
    """Read a report of this run: inside its new output directory and not older than it."""
    if not path.resolve().is_relative_to(request.output.resolve()):
        msg = f"report '{path.name}' is outside the output directory of the run"
        raise ReportError(msg)
    data = read_bounded(path)
    if path.stat().st_mtime < request.started - FRESHNESS_SLACK:
        msg = f"report '{path.name}' is older than the run"
        raise ReportError(msg)
    return data


def run_suite(
    runner: ProfileTests, request: SuiteRequest
) -> tuple[list[Diagnostic], SuiteRun | None]:
    """Run one suite and judge its results; return the run only if it is clean."""
    component = request.component.id
    try:
        run = runner.run(request)
        parse = PARSERS[run.results_format]
        results = parse(read_evidence(run.results, request), "test results")
    except ToolFailedError as error:
        return [error.diagnostic], None
    except ReportError as error:
        return [testing.invalid_evidence(component, request.suite, str(error))], None
    found = testing.judge(component, request.suite, run.returncode, results)
    if run.unisolated is not None:
        found.append(testing.unisolated(component, run.unisolated))
    if any(diagnostic.severity is Severity.ERROR for diagnostic in found):
        return found, None
    return found, run


def unit_coverage(
    runner: ProfileTests,
    request: SuiteRequest,
    run: SuiteRun,
    expected: coverage.Expectation,
    policy: Policy,
) -> tuple[list[Diagnostic], coverage.ComponentCoverage | None]:
    """Evaluate the coverage of a clean unit run against the policy floors."""
    component = request.component.id
    if run.coverage is None:
        problem = "the runner wrote no coverage report"
        return [testing.invalid_evidence(component, Suite.UNIT, problem)], None
    try:
        report = runner.coverage(read_evidence(run.coverage, request), request)
    except ReportError as error:
        return [testing.invalid_evidence(component, Suite.UNIT, str(error))], None
    summary, found = coverage.evaluate(expected, report, policy.coverage)
    return found, summary
