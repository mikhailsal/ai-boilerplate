"""R07.3 and R07.9: what the pre-commit hook accepts and rejects in a TypeScript component."""

from pathlib import Path

import pytest

from quality.testkit.policies import ComponentSpec
from quality.testkit.scratch import Project, create_project, output, rules_of
from quality.testkit.typescriptproject import CORE, TESTS, lock, package_json, pinned_packages

SOURCE = "web/src/core.ts"
TEST = "web/tests/core.test.ts"
TWICE = "\nexport function twice(value: number): number {\n  return value * 2;\n}\n"
TWICE_TEST = 'test("twice", () => {\n  expect(twice(2)).toBe(4);\n});\n'
# Twelve paths through one function: complexity 12 against a limit of 10.
LEVEL = (
    "\nexport function level(value: number): number {\n  let total = 0;\n"
    + "".join(f"  if (value > {n}) {{\n    total += 1;\n  }}\n" for n in range(11))
    + "  return total;\n}\n"
)
LEVEL_TEST = (
    'test("level", () => {\n  expect(level(20)).toBe(11);\n  expect(level(-1)).toBe(0);\n});\n'
)
# Five lines nothing runs, committed without the hook: an existing shortfall.
LEGACY = (
    "\nexport function legacy(value: number): number {\n  const a = value;\n"
    "  const b = a;\n  const c = b;\n  return c;\n}\n"
)
UNCOVERED = "export function unused(value: number): number {\n  return value + 1;\n}\n"
# Eight of nine new lines run, but not the early return: the changed lines miss
# their floor of 90% while the component's line and branch totals pass.
SCALE = """
export function scale(value: number, factor: number): number {
  const result = value * factor;
  if (result > 1000) {
    return 1000;
  }
  let total = result;
  total += 1;
  total -= 1;
  total *= 1;
  total /= 1;
  return total;
}
"""
SCALE_TEST = 'test("scale", () => {\n  expect(scale(2, 3)).toBe(6);\n});\n'
# Every line runs, but no condition is ever false.
ADJUST = """
export function adjust(value: number): number {
  let result = value;
  if (result > 0) {
    result += 1;
  }
  if (result > 1) {
    result += 1;
  }
  return result;
}
"""
ADJUST_TEST = 'test("adjust", () => {\n  expect(adjust(5)).toBe(7);\n});\n'
CURLY = '  {\n    rules: { curly: ["error", "multi"] },\n  },\n);\n'
# Two layers: the user interface may import the core, never the reverse.
ARCHITECTURE = """
[components.architecture]
layers = ["ui", "core"]

[[components.architecture.modules]]
name = "ui"
paths = ["src/ui/**"]

[[components.architecture.modules]]
name = "core"
paths = ["src/core/**"]
"""
MATH = "export function double(value: number): number {\n  return value * 2;\n}\n"
LABEL = """\
import { double } from "../core/math.ts";

export function label(value: number): string {
  return `x${String(double(value))}`;
}
"""
LABEL_TEST = """\
import { expect, test } from "vitest";

import { label } from "../src/ui/label.ts";

test("label", () => {
  expect(label(2)).toBe("x4");
});
"""
PREFIX = 'export const PREFIX = "x";\n'
UPWARD = 'import { PREFIX } from "../ui/prefix.ts";\n\n' + MATH.replace(
    "  return value * 2;", "  return PREFIX.length * value * 2;"
)


def with_test(names: str, body: str) -> str:
    """Return the sign test plus `body`, importing `names` beside `sign`."""
    return TESTS.replace("{ sign }", f"{{ {names} }}") + "\n" + body


def test_a_clean_change_is_committed(web: Project) -> None:
    before = web.head()
    web.write(SOURCE, CORE + TWICE)
    web.write(TEST, with_test("sign, twice", TWICE_TEST))
    result = web.commit("add twice")
    assert result.returncode == 0, output(result)
    assert web.head() != before
    assert "unit coverage of web: line 100.00%" in output(result)


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        (CORE.replace("return 1;", "return  1 ;"), "typescript.format"),
        (
            CORE.replace("    return -1;", "    Promise.resolve(value);\n    return -1;"),
            "typescript.lint",
        ),
        (CORE + "\nexport const zero: string = 0;\n", "typescript.types"),
    ],
    ids=["format", "typed-lint", "types"],
)
def test_static_findings_reject_the_commit(web: Project, text: str, rule: str) -> None:
    before = web.head()
    web.write(SOURCE, text)
    result = web.commit("bad change")
    assert result.returncode != 0
    assert rules_of(result) == {rule}, output(result)
    assert web.head() == before


def test_an_untyped_lint_configuration_rejects_the_commit(web: Project) -> None:
    web.write("web/eslint.config.js", 'export default [{ files: ["**/*.ts"] }];\n')
    result = web.commit("lint without type information", "web/eslint.config.js")
    assert result.returncode != 0
    assert rules_of(result) == {"typescript.lint"}, output(result)
    assert "ESLint lints this file without type information" in output(result)


def test_a_structure_finding_rejects_the_commit(web: Project) -> None:
    web.write(SOURCE, CORE + LEVEL)
    web.write(TEST, with_test("level, sign", LEVEL_TEST))
    result = web.commit("add level")
    assert result.returncode != 0
    assert rules_of(result) == {"structure.complexity"}, output(result)
    assert "web/src/core.ts" in output(result)


def test_a_failing_unit_test_rejects_the_commit(web: Project) -> None:
    web.write(TEST, TESTS.replace("toBe(1)", "toBe(2)"))
    result = web.commit("break a test")
    assert result.returncode != 0
    assert rules_of(result) == {"tests.failed"}, output(result)


def test_the_line_floor_applies_to_unchanged_code(web: Project) -> None:
    web.write(SOURCE, CORE + LEGACY)
    web.repo.git("add", "-A")
    web.repo.git("commit", "-q", "--no-verify", "-m", "legacy code")
    web.write(TEST, TESTS.replace("toBe(1);\n", "toBe(1);\n  expect(sign(0)).toBe(1);\n"))
    result = web.commit("touch only the tests")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.line"}, output(result)
    assert "changed lines not applicable" in output(result)


def test_a01_a_new_file_nothing_imports_must_be_covered(web: Project) -> None:
    web.write("web/src/extra.ts", UNCOVERED)
    result = web.commit("add an unimported file")
    assert result.returncode != 0
    assert "coverage.new-file" in rules_of(result)
    assert "new file 'web/src/extra.ts' has no unit coverage" in output(result)


def test_a04_uncovered_changed_lines_reject_the_commit(web: Project) -> None:
    web.write(SOURCE, CORE + SCALE)
    web.write(TEST, with_test("scale, sign", SCALE_TEST))
    result = web.commit("add scale")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.changed-lines"}, output(result)
    assert "changed lines 88.88% (8/9)" in output(result)


def test_a05_branch_coverage_fails_despite_full_line_coverage(web: Project) -> None:
    web.write(SOURCE, CORE + ADJUST)
    web.write(TEST, with_test("adjust, sign", ADJUST_TEST))
    result = web.commit("add adjust")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.branch"}, output(result)
    assert "line 100.00%" in output(result)


def test_a08_a_component_without_tests_fails(web: Project) -> None:
    web.repo.git("rm", "-q", TEST)
    result = web.git("commit", "-q", "-m", "delete the tests")
    assert result.returncode != 0
    assert "tests.none" in rules_of(result), output(result)


def test_a08_a_component_that_does_not_lock_its_coverage_driver_fails(web: Project) -> None:
    # Vitest itself stays locked as a peer of the coverage driver; the driver does not.
    driver = "@vitest/coverage-v8"
    pins = {name: version for name, version in pinned_packages().items() if name != driver}
    web.write("web/package.json", package_json("web", devDependencies=pins))
    lock(web.path / "web")
    result = web.commit("drop the coverage driver", "web/package.json", "web/package-lock.json")
    assert result.returncode != 0
    assert rules_of(result) == {"typescript.config"}, output(result)
    assert driver in output(result)


def test_a10_a_lint_configuration_change_reruns_the_component(web: Project) -> None:
    config = (web.path / "web" / "eslint.config.js").read_text()
    web.write("web/eslint.config.js", config.removesuffix(");\n") + CURLY)
    result = web.commit("require braces only where needed", "web/eslint.config.js")
    assert result.returncode != 0
    assert rules_of(result) == {"typescript.lint"}, output(result)


def test_a10_a_lockfile_change_reruns_the_suites(web: Project) -> None:
    lockfile = web.path / "web" / "package-lock.json"
    web.write("web/package-lock.json", lockfile.read_text().rstrip("\n") + "\n\n")
    result = web.commit("touch the lockfile", "web/package-lock.json")
    assert result.returncode == 0, output(result)
    assert "unit coverage of web" in output(result)


def test_imports_between_declared_modules_follow_the_layers(tmp_path: Path) -> None:
    spec = ComponentSpec(id="web", root="web", profile="typescript", extra=ARCHITECTURE)
    web = create_project(tmp_path / "project", spec)
    assert web.quality("bootstrap").returncode == 0
    web.write("web/src/core/math.ts", MATH)
    web.write("web/src/ui/label.ts", LABEL)
    web.write("web/tests/label.test.ts", LABEL_TEST)
    accepted = web.commit("the interface imports the core")
    assert accepted.returncode == 0, output(accepted)
    web.write("web/src/ui/prefix.ts", PREFIX)
    web.write("web/src/core/math.ts", UPWARD)
    rejected = web.commit("the core imports the interface")
    assert rejected.returncode != 0
    assert "architecture.forbidden-dependency" in rules_of(rejected), output(rejected)
    assert "web/src/core/math.ts" in output(rejected)
