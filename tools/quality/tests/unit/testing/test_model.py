from pathlib import Path

import pytest

from quality.policy import Component
from quality.testing import (
    CaseResult,
    Outcome,
    Suite,
    SuiteRequest,
    SuiteResults,
    SuiteRun,
    suite_roots,
)
from quality.testkit.policies import ComponentSpec, build_policy

ALL_SUITES = {
    "unit": ["tests/unit"],
    "integration": ["tests/integration", "tests/db"],
    "contract": ["tests/contract"],
    "e2e": ["tests/e2e"],
    "acceptance": ["tests/acceptance"],
}


def component(root: str = "services/api", tests: dict[str, list[str]] | None = None) -> Component:
    return Component.model_validate(
        {
            "id": "api",
            "role": "application",
            "profile": "python",
            "root": root,
            "source": ["src"],
            "tests": ALL_SUITES if tests is None else tests,
            "capabilities": ["http-api"],
        }
    )


def results(*outcomes: Outcome) -> SuiteResults:
    return SuiteResults(tuple(CaseResult(f"t{i}", o) for i, o in enumerate(outcomes)))


def test_results_count_cases_by_outcome() -> None:
    found = results(Outcome.PASSED, Outcome.FAILED, Outcome.ERROR, Outcome.SKIPPED, Outcome.PASSED)
    assert found.count(Outcome.PASSED) == 2
    assert found.count(Outcome.FAILED, Outcome.ERROR) == 2
    assert found.count() == 0
    assert (found.executed, found.failing) == (4, 2)


def test_skipped_cases_are_not_executed() -> None:
    assert results(Outcome.SKIPPED, Outcome.SKIPPED).executed == 0
    assert results().executed == 0
    assert results().failing == 0


@pytest.mark.parametrize(
    ("suite", "expected"),
    [
        (Suite.UNIT, ("tests/unit",)),
        (Suite.INTEGRATION, ("tests/integration", "tests/db")),
        (Suite.CONTRACT, ("tests/contract",)),
        (Suite.E2E, ("tests/e2e",)),
        (Suite.ACCEPTANCE, ("tests/acceptance",)),
    ],
)
def test_suite_roots_are_the_declared_roots_of_each_suite(
    suite: Suite, expected: tuple[str, ...]
) -> None:
    assert suite_roots(component(), suite) == expected


def test_undeclared_suites_have_no_roots() -> None:
    declared = build_policy(ComponentSpec(unit=("tests",))).components[0]
    assert suite_roots(declared, Suite.UNIT) == ("tests",)
    assert all(suite_roots(declared, suite) == () for suite in Suite if suite is not Suite.UNIT)


def test_every_suite_has_a_stable_name() -> None:
    assert [suite.value for suite in Suite] == list(ALL_SUITES)


@pytest.mark.parametrize(
    ("root", "expected"), [("services/api", "snap/services/api"), (".", "snap")]
)
def test_requests_run_in_the_component_root_of_the_snapshot(root: str, expected: str) -> None:
    request = SuiteRequest(
        component(root),
        Suite.UNIT,
        ("tests/unit",),
        Path("snap"),
        Path("work/out"),
        started=1.5,
        work=Path("work"),
    )
    assert request.directory == Path(expected)


def test_a_run_without_coverage_names_only_its_results() -> None:
    run = SuiteRun(1, Path("out/junit.xml"))
    assert run.coverage is None
    assert SuiteRun(0, Path("r"), Path("c")).coverage == Path("c")
