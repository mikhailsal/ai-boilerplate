"""R07.9: what the pre-commit hook accepts and rejects in a PHP component.

Xdebug reports a branch for each block of code it enters, so a branch is
missed only where a line runs without entering every block on it, as in a
ternary (decision 0005). The cases are sized with those semantics: each one
fails exactly the floor it names.
"""

import pytest

from quality.testkit.phpproject import CORE, TESTS, TYPED
from quality.testkit.scratch import Project, output, rules_of

SOURCE = "shop/src/Sign.php"
TEST = "shop/tests/SignTest.php"
TWICE = """
    public static function twice(int $value): int
    {
        return $value * 2;
    }
"""
TWICE_TEST = """
    public function testTwice(): void
    {
        self::assertSame(4, Sign::twice(2));
    }
"""
# Twelve paths through one method: complexity 12 against a limit of 10.
LEVEL = (
    "\n    public static function level(int $value): int\n    {\n        $total = 0;\n"
    + "".join(
        f"        if ($value > {n}) {{\n            $total += 1;\n        }}\n" for n in range(11)
    )
    + "        return $total;\n    }\n"
)
LEVEL_TEST = """
    public function testLevel(): void
    {
        self::assertSame(11, Sign::level(20));
        self::assertSame(0, Sign::level(-1));
    }
"""
# Five statements nothing runs, committed without the hook: an existing shortfall
# of lines (3/8), while the one branch it adds keeps the branch total at 3/4.
LEGACY = """
    public static function legacy(int $value): int
    {
        $a = $value + 1;
        $b = $a + 1;
        $c = $b + 1;
        $d = $c + 1;
        return $d + 1;
    }
"""
EXTRA = """\
<?php

declare(strict_types=1);

namespace App;

final class Extra
{
    public static function unused(int $value): int
    {
        return $value + 1;
    }
}
"""
# Seven of eight new lines run, but not the early return: the changed lines miss
# their floor of 90% while the component's line (10/11) and branch (5/6) totals pass.
SCALE = """
    public static function scale(int $value, int $factor): int
    {
        $result = $value * $factor;
        if ($result > 1000) {
            return intdiv($result, 1000);
        }
        $total = $result;
        $total += 1;
        $total -= 1;
        $total *= 1;
        return $total;
    }
"""
SCALE_TEST = """
    public function testScale(): void
    {
        self::assertSame(6, Sign::scale(2, 3));
    }
"""
# Every line runs, but no nested ternary is ever entered: branches 8/16.
ADJUST = """
    public static function adjust(int $value): int
    {
        $a = $value > 0 ? $value : ($value < -5 ? -5 : 0);
        $b = $value > 1 ? $value : ($value < -5 ? -5 : 1);
        return $a + $b;
    }
"""
ADJUST_TEST = """
    public function testAdjust(): void
    {
        self::assertSame(10, Sign::adjust(5));
    }
"""
EMPTY = TESTS.split("final class")[0].replace("use App\\Sign;\n", "") + (
    "final class SignTest extends TestCase {}\n"
)
EXCEPTION = """
[[exceptions]]
rule = "php.types"
path = "shop/src/Sign.php"
symbol = "parameter.phpDocType"
reason = "The documented type is kept for a caller that passes numeric strings."
owner = "shop maintainers"
review = 2027-01-01
"""


def with_method(text: str, body: str) -> str:
    """Return a class with the methods in `body` added at its end."""
    return text.removesuffix("}\n") + body + "}\n"


def test_a_clean_change_is_committed(shop: Project) -> None:
    before = shop.head()
    shop.write(SOURCE, with_method(CORE, TWICE))
    shop.write(TEST, with_method(TESTS, TWICE_TEST))
    result = shop.commit("add twice")
    assert result.returncode == 0, output(result)
    assert shop.head() != before
    assert "unit coverage of shop: line 100.00% (4/4), branch 100.00% (4/4)" in output(result)


@pytest.mark.parametrize(
    ("text", "rule", "message"),
    [
        (CORE.replace(": int\n    {", ": int {"), "php.format", "PER Coding Style"),
        (TYPED, "php.types", "[parameter.phpDocType]"),
    ],
    ids=["format", "types"],
)
def test_static_findings_reject_the_commit(
    shop: Project, text: str, rule: str, message: str
) -> None:
    before = shop.head()
    shop.write(SOURCE, text)
    result = shop.commit("bad change")
    assert result.returncode != 0
    assert rules_of(result) == {rule}, output(result)
    assert message in output(result)
    assert shop.head() == before


def test_a_reviewed_exception_accepts_one_analyzer_identifier_in_one_file(shop: Project) -> None:
    policy = (shop.path / "quality.toml").read_text()
    shop.write(SOURCE, TYPED)
    shop.write("quality.toml", policy + EXCEPTION)
    result = shop.commit("keep a documented type")
    assert result.returncode == 0, output(result)
    assert "1 findings covered by exceptions" in output(result)
    shop.write("shop/src/Other.php", TYPED.replace("class Sign", "class Other"))
    shop.write("shop/tests/OtherTest.php", TESTS.replace("Sign", "Other"))
    other = shop.commit("the same identifier in another file")
    assert other.returncode != 0
    assert rules_of(other) == {"php.types"}, output(other)
    assert "shop/src/Other.php:10" in output(other)


def test_a_structure_finding_rejects_the_commit(shop: Project) -> None:
    shop.write(SOURCE, with_method(CORE, LEVEL))
    shop.write(TEST, with_method(TESTS, LEVEL_TEST))
    result = shop.commit("add level")
    assert result.returncode != 0
    assert rules_of(result) == {"structure.complexity"}, output(result)
    assert "'Sign.level' has complexity 12" in output(result)


def test_a_failing_unit_test_rejects_the_commit(shop: Project) -> None:
    shop.write(TEST, TESTS.replace("assertSame(1, Sign::of(4))", "assertSame(2, Sign::of(4))"))
    result = shop.commit("break a test")
    assert result.returncode != 0
    assert rules_of(result) == {"tests.failed"}, output(result)


def test_the_line_floor_applies_to_unchanged_code(shop: Project) -> None:
    shop.write(SOURCE, with_method(CORE, LEGACY))
    shop.repo.git("add", "-A")
    shop.repo.git("commit", "-q", "--no-verify", "-m", "legacy code")
    extra = "        self::assertSame(1, Sign::of(0));\n    }\n"
    shop.write(TEST, TESTS.replace("    }\n", extra, 1))
    result = shop.commit("touch only the tests")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.line"}, output(result)
    assert "line 37.50% (3/8)" in output(result)
    assert "changed lines not applicable" in output(result)


def test_a01_a_new_class_nothing_uses_must_be_covered(shop: Project) -> None:
    shop.write("shop/src/Extra.php", EXTRA)
    result = shop.commit("add an unused class")
    assert result.returncode != 0
    assert "coverage.new-file" in rules_of(result)
    assert "new file 'shop/src/Extra.php' has no unit coverage" in output(result)


def test_a04_uncovered_changed_lines_reject_the_commit(shop: Project) -> None:
    shop.write(SOURCE, with_method(CORE, SCALE))
    shop.write(TEST, with_method(TESTS, SCALE_TEST))
    result = shop.commit("add scale")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.changed-lines"}, output(result)
    assert "changed lines 87.50% (7/8)" in output(result)


def test_a05_branch_coverage_fails_despite_full_line_coverage(shop: Project) -> None:
    shop.write(SOURCE, with_method(CORE, ADJUST))
    shop.write(TEST, with_method(TESTS, ADJUST_TEST))
    result = shop.commit("add adjust")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.branch"}, output(result)
    assert "line 100.00% (6/6), branch 50.00% (8/16)" in output(result)


def test_a08_a_component_without_tests_fails(shop: Project) -> None:
    shop.write(TEST, EMPTY)
    result = shop.commit("empty the tests")
    assert result.returncode != 0
    assert rules_of(result) == {"tests.none"}, output(result)


def test_a08_a_deleted_test_root_fails(shop: Project) -> None:
    shop.repo.git("rm", "-q", TEST)
    result = shop.git("commit", "-q", "-m", "delete the tests")
    assert result.returncode != 0
    assert "discovery.missing-root" in rules_of(result), output(result)
