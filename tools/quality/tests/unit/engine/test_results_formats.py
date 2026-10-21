import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from quality.catalog import build_registry
from quality.engine import SuiteSettings, run_suites
from quality.gitio import staged
from quality.policy import Profile
from quality.testing import ResultsFormat, Suite, SuiteRequest, SuiteRun
from quality.testkit.gitrepo import GitRepo
from quality.testkit.policies import policy_toml
from quality.testkit.reports import FileSpec
from quality.testkit.suites import Script, ScriptedRunner

RULES = {rule.id: rule for rule in build_registry()}
FULL = {
    "src/app/__init__.py": FileSpec.first(0, 0),
    "src/app/core.py": FileSpec.first(2, 2, (1, 1)),
}


def dart_events(*results: str) -> bytes:
    events: list[object] = [{"type": "suite", "suite": {"id": 0, "path": "test/a_test.dart"}}]
    for number, result in enumerate(results, 1):
        events.append({"type": "testStart", "test": {"id": number, "name": "t", "suiteID": 0}})
        events.append({"type": "testDone", "testID": number, "result": result, "hidden": False})
    events.append({"type": "done"})
    return b"\n".join(json.dumps(event).encode() for event in events)


def dart_hook(data: bytes) -> Callable[[SuiteRequest, SuiteRun], SuiteRun]:
    def hook(_request: SuiteRequest, done: SuiteRun) -> SuiteRun:
        results = done.results.with_name("results.json")
        results.write_bytes(data)
        return replace(done, results=results, results_format=ResultsFormat.DART_JSON)

    return hook


@pytest.mark.parametrize(
    ("data", "rules"),
    [
        (dart_events("success"), []),
        (dart_events("success", "failure"), ["tests.failed"]),
        (dart_events(), ["tests.none"]),
        (b'{"type": "suite"}', ["tests.evidence"]),
    ],
)
def test_the_engine_parses_results_in_the_format_the_runner_names(
    tmp_path: Path, data: bytes, rules: list[str]
) -> None:
    repo = GitRepo.create(tmp_path / "repo")
    repo.write("quality.toml", policy_toml())
    repo.write("src/app/__init__.py", "")
    repo.write("src/app/core.py", "def add(a, b):\n    return a + b\n")
    repo.write("tests/test_core.py", "def test_value():\n    assert True\n")
    repo.git("add", "-A")
    tests = ScriptedRunner({("app", Suite.UNIT): Script(files=FULL)}, dart_hook(data))
    git = repo.repository()
    report = run_suites(git, staged(git), SuiteSettings({Profile.PYTHON: tests}, RULES))
    assert [diagnostic.rule for diagnostic in report.diagnostics] == rules
