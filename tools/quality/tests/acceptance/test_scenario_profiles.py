"""R08: what each Tier 1 runner reports that must not prove a scenario.

A component of each profile declares the library capability with one
scenario mapped to its `sign` test. The mapping is committed first, which
proves the profile's case names; then a runner feature that would make the
test look successful without running it is rejected.
"""

from quality.testkit.dartproject import TESTS as DART_TESTS
from quality.testkit.phpproject import TESTS as PHP_TESTS
from quality.testkit.scenarios import ScenarioSpec, manifest_toml
from quality.testkit.scratch import Project, output, rules_of
from quality.testkit.typescriptproject import TESTS as TYPESCRIPT_TESTS

NO_BOUNDARY = 'no_boundary_reason = "pure computation without external boundaries"'
LIBRARY = 'capabilities = ["library"]\nscenarios = "scenarios.toml"'


def declare(project: Project, component: str, case: str) -> None:
    """Declare the library capability with one scenario that maps `case`, and commit it."""
    policy = (project.path / "quality.toml").read_text(encoding="utf-8")
    project.write("quality.toml", policy.replace(NO_BOUNDARY, LIBRARY))
    scenario = ScenarioSpec("sign", (case,), requirements=("library.public-api",))
    project.write(f"{component}/scenarios.toml", manifest_toml(scenario, component=component))
    result = project.commit("declare the public API scenario")
    assert result.returncode == 0, output(result)
    assert f"scenarios of {component}: 1 of 1 proved" in output(result)


def rejected(project: Project, message: str) -> tuple[set[str], str]:
    before = project.head()
    result = project.commit(message)
    assert result.returncode != 0, output(result)
    assert project.head() == before
    return rules_of(result), output(result)


TYPESCRIPT_CASE = "tests/core.test.ts::sign"
POSITIVE = '\ntest("positive", () => {\n  expect(sign(4)).toBe(1);\n});\n'


def test_a_vitest_inverted_test_does_not_prove_its_scenario(web: Project) -> None:
    declare(web, "web", TYPESCRIPT_CASE)
    inverted = TYPESCRIPT_TESTS.replace('test("sign"', 'test.fails("sign"').replace(
        "toBe(-1)", "toBe(1)"
    )
    web.write("web/tests/core.test.ts", inverted + POSITIVE)
    rules, text = rejected(web, "invert the sign test")
    assert rules == {"tests.skipped", "scenarios.skipped"}, text
    assert f"'{TYPESCRIPT_CASE}' was expected to fail" in text


def test_a_vitest_retry_cannot_turn_a_failure_into_a_pass(web: Project) -> None:
    declare(web, "web", TYPESCRIPT_CASE)
    retried = 'let runs = 0;\n\ntest("sign", { retry: 2 }, () => {\n  runs += 1;\n'
    flaky = TYPESCRIPT_TESTS.replace(
        'test("sign", () => {\n', retried + "  expect(runs).toBe(2);\n"
    )
    web.write("web/tests/core.test.ts", flaky + POSITIVE)
    rules, text = rejected(web, "retry the sign test")
    assert rules == {"tests.failed", "scenarios.failed"}, text


def test_a_dart_solo_test_skips_the_mapped_one(calc: Project) -> None:
    declare(calc, "calc", "test/core_test.dart::sign")
    solo = "  test('positive', () {\n    expect(sign(4), 1);\n  }, solo: true);\n}\n"
    calc.write(
        "calc/test/core_test.dart", DART_TESTS.format(name="calc").removesuffix("}\n") + solo
    )
    rules, text = rejected(calc, "focus on one test")
    # The analyzer reports `solo` too, as a member that must not be submitted.
    assert {"tests.focused", "scenarios.skipped", "dart.types"} <= rules, text
    assert rules <= {"tests.focused", "tests.skipped", "scenarios.skipped", "dart.types"}, text


def test_a_phpunit_skip_does_not_prove_its_scenario(shop: Project) -> None:
    declare(shop, "shop", "App.Tests.SignTest::testSign")
    # A requirement no PHP 8 meets skips the test at run time, unlike a
    # `markTestSkipped` call, which PHPStan reports as leaving unreachable code;
    # a copy under another name keeps the coverage.
    copy = PHP_TESTS[PHP_TESTS.index("    public function") :].replace("testSign", "testCopy")
    requires = "    #[\\PHPUnit\\Framework\\Attributes\\RequiresPhp('< 8.0.0')]\n"
    skipped = PHP_TESTS.replace(
        "    public function testSign", requires + "    public function testSign"
    )
    shop.write("shop/tests/SignTest.php", skipped.removesuffix("}\n") + "\n" + copy)
    rules, text = rejected(shop, "skip the sign test")
    assert rules == {"tests.skipped", "scenarios.skipped"}, text
    assert "'App.Tests.SignTest::testSign' was skipped" in text
