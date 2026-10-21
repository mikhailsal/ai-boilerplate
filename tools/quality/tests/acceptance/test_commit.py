"""R07: what the pre-commit hook accepts and rejects in a Python component."""

import pytest

from quality.testkit.scratch import CORE, Project, output, rules_of

TESTS = "app/tests/test_app.py"
SOURCE = "app/src/app/core.py"
SIGN_TEST = """\
from app.core import sign


def test_sign() -> None:
    assert sign(-3) == -1
    assert sign(4) == 1
"""
# Ten covered functions: two lines each, so twenty new covered lines.
BIG = "".join(f"\n\ndef plus_{n}(value: int) -> int:\n    return value + {n}\n" for n in range(10))
BIG_TEST = """\
from app import big


def test_big() -> None:
    assert [getattr(big, f"plus_{n}")(0) for n in range(10)] == list(range(10))
"""
UNCOVERED = "def unused(value: int) -> int:\n    return value + 1\n"
# Seven of nine new lines run: 78% of the changed lines, 85% of all lines, 75% of branches.
SCALE = """

def scale(value: int, factor: int) -> int:
    result = value * factor
    if result > 1000:
        result = 1000
        return result
    total = result
    total += 1
    total -= 1
    return total
"""
SCALE_TEST = SIGN_TEST + "\n\ndef test_scale() -> None:\n    assert scale(2, 3) == 6\n"
# Every line runs, but no condition is ever false: 5 of 8 branches overall.
ADJUST = """

def adjust(value: int) -> int:
    if value > 0:
        value += 1
    if value > 1:
        value += 1
    if value > 2:
        value += 1
    return value
"""
ADJUST_TEST = SIGN_TEST + "\n\ndef test_adjust() -> None:\n    assert adjust(5) == 8\n"
HALF = "\n\ndef half(value: int) -> str:\n    return value // 2\n"


def with_import(test: str, name: str) -> str:
    return test.replace("import sign", f"import {', '.join(sorted((name, 'sign')))}")


def test_a_clean_change_is_committed(hooked: Project) -> None:
    before = hooked.head()
    hooked.write(SOURCE, CORE + "\n\ndef twice(value: int) -> int:\n    return value * 2\n")
    test = SIGN_TEST + "\n\ndef test_twice() -> None:\n    assert twice(2) == 4\n"
    hooked.write(TESTS, with_import(test, "twice"))
    result = hooked.commit("add twice")
    assert result.returncode == 0, output(result)
    assert hooked.head() != before
    assert "changed lines 100.00% (2/2)" in output(result)


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        (CORE.replace("(value: int) -> int", "(value:int)->int"), "python.format"),
        ("import os\n\n\n" + CORE, "python.lint"),
        (CORE + HALF, "python.types"),
    ],
    ids=["format", "lint", "types"],
)
def test_static_findings_reject_the_commit(hooked: Project, text: str, rule: str) -> None:
    before = hooked.head()
    hooked.write(SOURCE, text)
    if "half" in text:
        test = SIGN_TEST + "\n\ndef test_half() -> None:\n    assert half(4) == 2\n"
        hooked.write(TESTS, with_import(test, "half"))
    result = hooked.commit("bad change")
    assert result.returncode != 0
    assert rule in rules_of(result), output(result)
    assert hooked.head() == before


def test_a01_a_new_file_nothing_imports_must_be_covered(hooked: Project) -> None:
    hooked.write("app/src/app/extra.py", UNCOVERED)
    result = hooked.commit("add an unimported file")
    assert result.returncode != 0
    assert "coverage.new-file" in rules_of(result)
    assert "new file 'app/src/app/extra.py' has no unit coverage" in output(result)


def test_a02_a_covered_sibling_cannot_compensate(hooked: Project) -> None:
    hooked.write("app/src/app/big.py", BIG.lstrip())
    hooked.write("app/tests/test_big.py", BIG_TEST)
    hooked.write("app/src/app/extra.py", UNCOVERED)
    result = hooked.commit("add a covered and an uncovered file")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.new-file"}, output(result)


def test_a04_uncovered_changed_lines_reject_the_commit(hooked: Project) -> None:
    hooked.write(SOURCE, CORE + SCALE)
    hooked.write(TESTS, with_import(SCALE_TEST, "scale"))
    result = hooked.commit("add scale")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.changed-lines"}, output(result)


def test_a05_branch_coverage_fails_despite_full_line_coverage(hooked: Project) -> None:
    hooked.write(SOURCE, CORE + ADJUST)
    hooked.write(TESTS, with_import(ADJUST_TEST, "adjust"))
    result = hooked.commit("add adjust")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.branch"}, output(result)
    assert "line 100.00%" in output(result)


@pytest.mark.parametrize(
    ("old", "new", "rule"),
    [
        ('select = ["E", "F", "I"]', 'select = ["E", "F", "I", "D"]', "python.lint"),
        ('pythonpath = ["src"]', 'pythonpath = ["tests"]', "tests.failed"),
    ],
    ids=["ruff", "pytest"],
)
def test_a10_a_configuration_change_reruns_the_component(
    hooked: Project, old: str, new: str, rule: str
) -> None:
    config = hooked.path / "app" / "pyproject.toml"
    hooked.write("app/pyproject.toml", config.read_text().replace(old, new))
    result = hooked.commit("change the configuration", "app/pyproject.toml")
    assert result.returncode != 0
    assert rule in rules_of(result), output(result)


def test_a10_a_lockfile_change_reruns_the_suites(hooked: Project) -> None:
    lock = hooked.path / "app" / "uv.lock"
    hooked.write("app/uv.lock", lock.read_text() + "# reviewed\n")
    result = hooked.commit("touch the lockfile", "app/uv.lock")
    assert result.returncode == 0, output(result)
    assert "unit coverage of app" in output(result)


@pytest.mark.parametrize("name", ["setup.py", "conftest.py"])
def test_modules_named_like_configuration_are_checked_as_source(hooked: Project, name: str) -> None:
    hooked.write(f"app/src/app/{name}", "import os\n")
    result = hooked.commit("add a module named like a configuration script")
    assert result.returncode != 0
    assert {"python.lint", "coverage.new-file"} <= rules_of(result), output(result)
