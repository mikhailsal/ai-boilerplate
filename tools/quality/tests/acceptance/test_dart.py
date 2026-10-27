"""R07.9: what the pre-commit hook accepts and rejects in a Dart VM component.

Dart reports a line only where code runs a call or enters a function, and a
branch where a block is entered (decision 0005). The cases are sized with those
semantics: each one fails exactly the floor it names.
"""

import pytest

from quality.testkit.dartproject import CORE, TESTS, lock, pinned_packages, pubspec
from quality.testkit.scratch import Project, output, rules_of

SOURCE = "calc/lib/core.dart"
TEST = "calc/test/core_test.dart"
SIGN_TEST = TESTS.format(name="calc")
TWICE = "\nint twice(int value) => value * 2;\n"
TWICE_TEST = "  test('twice', () => expect(twice(2), 4));\n"
# Twelve paths through one function: complexity 12 against a limit of 10.
LEVEL = (
    "\nint level(int value) {\n  var total = 0;\n"
    + "".join(f"  if (value > {n}) {{\n    total += 1;\n  }}\n" for n in range(11))
    + "  return total;\n}\n"
)
LEVEL_TEST = "  test('level', () {\n    expect(level(20), 11);\n    expect(level(-1), 0);\n  });\n"
# Six lines nothing runs, committed without the hook: an existing shortfall of
# lines, while the one branch it adds keeps the branch total at 3/4.
LEGACY = """
int legacy(int value) {
  final a = value + 1;
  final b = a + 1;
  final c = b + 1;
  final d = c + 1;
  return d + 1;
}
"""
UNCOVERED = "int unused(int value) {\n  return value + 1;\n}\n"
# Eight of nine new lines run, but not the early return: the changed lines miss
# their floor of 90% while the component's line (11/12) and branch (4/5) totals pass.
SCALE = """
int scale(int value, int factor) {
  final result = value * factor;
  if (result > 1000) {
    return result ~/ 1000;
  }
  var total = result;
  total += 1;
  total -= 1;
  total *= 1;
  total += 2;
  total -= 2;
  return total;
}
"""
SCALE_TEST = "  test('scale', () => expect(scale(2, 3), 6));\n"
# Every line runs, but no `else` block is ever entered: branches 8/12.
ADJUST = (
    "\nint adjust(int value) {\n  var result = value;\n"
    + "".join(
        f"  if (result > {n}) {{\n    result += 1;\n  }} else {{\n    result = 0;\n  }}\n"
        for n in range(4)
    )
    + "  return result;\n}\n"
)
ADJUST_TEST = "  test('adjust', () => expect(adjust(5), 9));\n"


def with_test(body: str) -> str:
    """Return the sign test plus the test cases in `body`."""
    return SIGN_TEST.removesuffix("}\n") + body + "}\n"


def test_a_clean_change_is_committed(calc: Project) -> None:
    before = calc.head()
    calc.write(SOURCE, CORE + TWICE)
    calc.write(TEST, with_test(TWICE_TEST))
    result = calc.commit("add twice")
    assert result.returncode == 0, output(result)
    assert calc.head() != before
    assert "unit coverage of calc: line 100.00%" in output(result)


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        (CORE.replace("return 1;", "return  1 ;"), "dart.format"),
        (CORE + "\nString? label = null;\n", "dart.lint"),
        (CORE + "\nconst List empty = [];\n", "dart.types"),
    ],
    ids=["format", "lint", "strict-types"],
)
def test_static_findings_reject_the_commit(calc: Project, text: str, rule: str) -> None:
    before = calc.head()
    calc.write(SOURCE, text)
    result = calc.commit("bad change")
    assert result.returncode != 0
    assert rules_of(result) == {rule}, output(result)
    assert calc.head() == before


def test_a_compile_error_rejects_the_commit(calc: Project) -> None:
    calc.write(SOURCE, CORE + "\nint zero() => 'zero';\n")
    result = calc.commit("return a string as an int")
    assert result.returncode != 0
    assert "dart.types" in rules_of(result), output(result)
    assert "return_of_invalid_type" in output(result)


def test_a_structure_finding_rejects_the_commit(calc: Project) -> None:
    calc.write(SOURCE, CORE + LEVEL)
    calc.write(TEST, with_test(LEVEL_TEST))
    result = calc.commit("add level")
    assert result.returncode != 0
    assert rules_of(result) == {"structure.complexity"}, output(result)
    assert SOURCE in output(result)


def test_a_failing_unit_test_rejects_the_commit(calc: Project) -> None:
    calc.write(TEST, SIGN_TEST.replace("expect(sign(4), 1);", "expect(sign(4), 2);"))
    result = calc.commit("break a test")
    assert result.returncode != 0
    assert rules_of(result) == {"tests.failed"}, output(result)


def test_the_line_floor_applies_to_unchanged_code(calc: Project) -> None:
    calc.write(SOURCE, CORE + LEGACY)
    calc.repo.git("add", "-A")
    calc.repo.git("commit", "-q", "--no-verify", "-m", "legacy code")
    extra = "    expect(sign(4), 1);\n    expect(sign(0), 1);\n"
    calc.write(TEST, SIGN_TEST.replace("    expect(sign(4), 1);\n", extra))
    result = calc.commit("touch only the tests")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.line"}, output(result)
    assert "changed lines not applicable" in output(result)


def test_a01_a_new_file_nothing_imports_must_be_covered(calc: Project) -> None:
    calc.write("calc/lib/extra.dart", UNCOVERED)
    result = calc.commit("add an unimported file")
    assert result.returncode != 0
    assert "coverage.new-file" in rules_of(result)
    assert "new file 'calc/lib/extra.dart' has no unit coverage" in output(result)


def test_a04_uncovered_changed_lines_reject_the_commit(calc: Project) -> None:
    calc.write(SOURCE, CORE + SCALE)
    calc.write(TEST, with_test(SCALE_TEST))
    result = calc.commit("add scale")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.changed-lines"}, output(result)
    assert "changed lines 88.88% (8/9)" in output(result)


def test_a05_branch_coverage_fails_despite_full_line_coverage(calc: Project) -> None:
    calc.write(SOURCE, CORE + ADJUST)
    calc.write(TEST, with_test(ADJUST_TEST))
    result = calc.commit("add adjust")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.branch"}, output(result)
    assert "line 100.00%" in output(result)


def test_a08_a_component_without_tests_fails(calc: Project) -> None:
    calc.write(TEST, "void main() {}\n")
    result = calc.commit("empty the tests")
    assert result.returncode != 0
    assert "tests.none" in rules_of(result), output(result)


def test_a08_a_deleted_test_root_fails(calc: Project) -> None:
    calc.repo.git("rm", "-q", TEST)
    result = calc.git("commit", "-q", "-m", "delete the tests")
    assert result.returncode != 0
    assert {"discovery.missing-root", "tests.failed"} <= rules_of(result), output(result)


def test_a08_a_component_that_does_not_lock_the_test_runner_fails(calc: Project) -> None:
    pins = {name: version for name, version in pinned_packages().items() if name != "test"}
    calc.write("calc/pubspec.yaml", pubspec("calc", pinned=False, dev_dependencies=pins))
    lock(calc.path / "calc")
    result = calc.commit("drop the test runner", "calc/pubspec.yaml", "calc/pubspec.lock")
    assert result.returncode != 0
    assert rules_of(result) == {"dart.config"}, output(result)
    assert "test" in output(result)
    assert "1.33.0" in output(result)


@pytest.mark.parametrize(
    ("lint", "rule"),
    [("public_member_api_docs", "dart.lint"), ("prefer_final_parameters", "dart.config")],
    ids=["new-lint", "deprecated-lint"],
)
def test_a10_an_analysis_options_change_reruns_the_component(
    calc: Project, lint: str, rule: str
) -> None:
    options = calc.path / "calc" / "analysis_options.yaml"
    enabled = options.read_text() + f"\nlinter:\n  rules:\n    - {lint}\n"
    calc.write("calc/analysis_options.yaml", enabled)
    result = calc.commit("enable a lint", "calc/analysis_options.yaml")
    assert result.returncode != 0
    assert rules_of(result) == {rule}, output(result)
    assert lint in output(result)


def test_a10_a_lockfile_change_reruns_the_suites(calc: Project) -> None:
    lockfile = calc.path / "calc" / "pubspec.lock"
    calc.write("calc/pubspec.lock", lockfile.read_text().rstrip("\n") + "\n\n")
    result = calc.commit("touch the lockfile", "calc/pubspec.lock")
    assert result.returncode == 0, output(result)
    assert "unit coverage of calc" in output(result)
