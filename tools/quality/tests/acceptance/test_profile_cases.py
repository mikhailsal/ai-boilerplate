"""R07.9: the remaining Python profile cases through real hooks, one finding at a time."""

from pathlib import Path

from quality.testkit.scratch import CORE, Project, component, create_project, output, rules_of

SOURCE = "app/src/app/core.py"
TESTS = "app/tests/test_app.py"
# Twelve paths through one function: complexity 12 against a limit of 10.
LEVEL = (
    "\n\ndef level(value: int) -> int:\n    total = 0\n"
    + "".join(f"    if value > {n}:\n        total += 1\n" for n in range(11))
    + "    return total\n"
)
LEVEL_TEST = """\
from app.core import level, sign


def test_sign() -> None:
    assert sign(-3) == -1
    assert sign(4) == 1


def test_level() -> None:
    assert level(20) == 11
    assert level(-1) == 0
"""
# Five lines nothing runs, committed without the hook: an existing shortfall.
LEGACY = "\n\ndef legacy(value: int) -> int:\n    a = value\n    b = a\n    c = b\n    return c\n"


def test_a_structure_finding_rejects_the_commit(hooked: Project) -> None:
    hooked.write(SOURCE, CORE + LEVEL)
    hooked.write(TESTS, LEVEL_TEST)
    result = hooked.commit("add level")
    assert result.returncode != 0
    assert rules_of(result) == {"structure.complexity"}, output(result)


def test_a_failing_unit_test_rejects_the_commit(hooked: Project) -> None:
    hooked.write(TESTS, (hooked.path / TESTS).read_text().replace("== 1", "== 2"))
    result = hooked.commit("break a test")
    assert result.returncode != 0
    assert rules_of(result) == {"tests.failed"}, output(result)


def test_the_line_floor_applies_to_unchanged_code(hooked: Project) -> None:
    hooked.write(SOURCE, CORE + LEGACY)
    hooked.repo.git("add", "-A")
    hooked.repo.git("commit", "-q", "--no-verify", "-m", "legacy code")
    hooked.write(TESTS, (hooked.path / TESTS).read_text() + "    assert sign(0) == 1\n")
    result = hooked.commit("touch only the tests")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.line"}, output(result)
    assert "changed lines not applicable" in output(result)


def test_each_component_is_tested_and_counted_on_its_own(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", component("app"), component("lib"))
    assert project.quality("bootstrap").returncode == 0
    project.write("lib/src/lib/extra.py", "def unused(value: int) -> int:\n    return value\n")
    rejected = project.commit("add uncovered code to lib")
    assert rejected.returncode != 0
    assert "coverage.new-file" in rules_of(rejected)
    assert "[lib]" in output(rejected)
    assert "[app]" not in output(rejected)
    assert "unit coverage of app" not in output(rejected)
    project.repo.git("rm", "-q", "--cached", "lib/src/lib/extra.py")
    (project.path / "lib/src/lib/extra.py").unlink()
    project.write("app/src/app/core.py", "# The sign of a number.\n" + CORE)
    accepted = project.commit("document app", "app/src/app/core.py")
    assert accepted.returncode == 0, output(accepted)
    assert "unit coverage of app" in output(accepted)
    assert "unit coverage of lib" not in output(accepted)
