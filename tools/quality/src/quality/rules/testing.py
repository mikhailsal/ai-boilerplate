"""Test execution evidence: a suite passes only with a successful run of real tests (R06)."""

from __future__ import annotations

from quality.diagnostics import Diagnostic, Kind, Rule, Severity
from quality.testing import Outcome, Suite, SuiteResults

FAILED = Rule(
    id="tests.failed",
    title="Tests failed",
    requirement="R06",
    explanation=(
        "A suite passes only when its runner exits successfully and no test fails or "
        "errors. Coverage written by a failed run is discarded, never evaluated."
    ),
    remedy="Fix the failing tests or the code they test, then rerun the check.",
)
NONE = Rule(
    id="tests.none",
    title="A mandatory suite ran no tests",
    requirement="R06",
    explanation=(
        "Every component declares unit test roots, and its unit suite must execute at "
        "least one test. A missing root, an empty selection, or only skipped tests fails."
    ),
    remedy="Add unit tests under the declared roots, or correct the roots in quality.toml.",
)
SKIPPED = Rule(
    id="tests.skipped",
    title="Tests were skipped",
    requirement="R06",
    explanation="Skipped tests do not count as executed; the suite still needs passing tests.",
    remedy="Remove the skip or make the test runnable in the unit environment.",
    severity=Severity.WARNING,
)
EVIDENCE = Rule(
    id="tests.evidence",
    title="Test evidence is missing or invalid",
    requirement="R06",
    explanation=(
        "Results and coverage must come from this run: the reports are written to a new "
        "empty directory, must exist when the runner exits, must be parseable and "
        "consistent, and must name only files of the snapshot."
    ),
    remedy="Check the profile's test runner and configuration, then rerun the check.",
    kind=Kind.ENVIRONMENT,
)
NETWORK = Rule(
    id="tests.network",
    title="A unit suite ran with network access",
    requirement="R06",
    explanation=(
        "Unit suites run in a network namespace with loopback only, so a test cannot "
        "reach a real service or the internet. This system does not let an unprivileged "
        "user create that namespace, so the suite ran with the network."
    ),
    remedy=(
        "Allow unprivileged user namespaces (on Ubuntu, set the sysctl "
        "kernel.apparmor_restrict_unprivileged_userns to 0), or review that the unit "
        "tests use no network."
    ),
    severity=Severity.WARNING,
)
RULES = (FAILED, NONE, SKIPPED, EVIDENCE, NETWORK)
# A failing suite names at most this many of its failing cases.
NAMED = 5


def _failures(results: SuiteResults) -> str:
    names = [case.name for case in results.cases if case.outcome in (Outcome.FAILED, Outcome.ERROR)]
    if not names:
        return ""
    more = len(names) - NAMED
    return "; failed: " + ", ".join(names[:NAMED]) + (f", and {more} more" if more > 0 else "")


def judge(component: str, suite: Suite, returncode: int, results: SuiteResults) -> list[Diagnostic]:
    """Report the run of one suite; its coverage may be used only if no finding is an error."""
    where = f"the {suite} suite of '{component}'"
    found: list[Diagnostic] = []
    if results.executed == 0:
        message = f"{where} executed no tests (runner exit status {returncode})"
        found.append(NONE.diagnostic(message, component=component))
    elif results.failing or returncode != 0:
        message = (
            f"{where}: {results.failing} of {results.executed} tests failed; "
            f"runner exit status {returncode}{_failures(results)}"
        )
        found.append(FAILED.diagnostic(message, component=component))
    if skipped := results.count(Outcome.SKIPPED):
        message = f"{where} skipped {skipped} tests"
        found.append(SKIPPED.diagnostic(message, component=component))
    return found


def missing_suite(component: str) -> Diagnostic:
    """Report a component without unit test roots."""
    message = f"'{component}' declares no unit test roots"
    return NONE.diagnostic(message, component=component)


def invalid_evidence(component: str, suite: Suite, problem: str) -> Diagnostic:
    """Report evidence that cannot be trusted; the run counts as not having passed."""
    return EVIDENCE.diagnostic(
        f"the {suite} suite of '{component}': {problem}", component=component
    )


def unisolated(component: str, reason: str) -> Diagnostic:
    """Report a unit suite that ran without network isolation."""
    message = f"the unit suite of '{component}' ran with the network: {reason}"
    return NETWORK.diagnostic(message, component=component)
