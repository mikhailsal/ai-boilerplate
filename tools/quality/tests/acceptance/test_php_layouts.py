"""R07.9 and R06.3 in other PHP layouts: components, autoload roots, and scripts.

The gate loads every source file that only declares, so a class no test uses
is still measured; a file that runs code when it is loaded is left to the
tests, and its functions count as unmeasured until one loads it (decision 0013).
"""

import json
from dataclasses import replace
from pathlib import Path

from quality.boundedio import JsonValue
from quality.testkit.phpproject import CORE, TESTS, manifest
from quality.testkit.scratch import Project, component, create_project, output, php, rules_of

UNUSED = """\
<?php

declare(strict_types=1);

namespace {namespace};

final class Unused
{{
    public static function unused(int $value): int
    {{
        return $value + 1;
    }}
}}
"""
WORDS = """\
<?php

declare(strict_types=1);

namespace Words;

final class Shout
{
    public static function of(string $text): string
    {
        return strtoupper($text);
    }
}
"""
WORDS_TEST = """\
<?php

declare(strict_types=1);

namespace App\\Tests;

use PHPUnit\\Framework\\TestCase;
use Words\\Shout;

final class ShoutTest extends TestCase
{
    public function testShout(): void
    {
        self::assertSame('HI', Shout::of('hi'));
    }
}
"""
# One-line methods break PER Coding Style, but their statements still count.
ONE_LINE = """
    public static function twice(int $value): int { return $value * 2; }

    public static function thrice(int $value): int { return $value * 3; }
"""
ONE_LINE_TEST = """
    public function testTwice(): void
    {
        self::assertSame(4, Sign::twice(2));
    }
"""
SCRIPT = """\
<?php

declare(strict_types=1);

function greet(string $name): string
{
    return "hello {$name}";
}

$greeting = greet('php');
"""
SCRIPT_TEST = """\
<?php

declare(strict_types=1);

namespace App\\Tests;

use PHPUnit\\Framework\\TestCase;

final class GreetTest extends TestCase
{
    public function testGreet(): void
    {
        require_once __DIR__ . '/../src/greet.php';
        self::assertSame('hello you', \\greet('you'));
    }
}
"""
IGNORED = """
    /** @codeCoverageIgnore */
    public static function ignored(int $value): int
    {
        return $value + 1;
    }
"""


def bootstrapped(project: Project) -> Project:
    """Install the hooks and fill the caches; return the project."""
    result = project.quality("bootstrap")
    assert result.returncode == 0, output(result)
    return project


def with_method(text: str, body: str) -> str:
    """Return a class with the methods in `body` added at its end."""
    return text.removesuffix("}\n") + body + "}\n"


def test_every_component_is_tested_and_a_failure_in_the_second_blocks(tmp_path: Path) -> None:
    project = bootstrapped(create_project(tmp_path / "project", php("a"), php("b")))
    result = project.quality("check", "--all")
    assert result.returncode == 0, output(result)
    assert "unit coverage of a: line 100.00%" in output(result)
    assert "unit coverage of b: line 100.00%" in output(result)
    project.write("b/tests/SignTest.php", TESTS.replace("Sign::of(4)", "Sign::of(-4)"))
    rejected = project.commit("break a test of the second component")
    assert rejected.returncode != 0
    assert rules_of(rejected) == {"tests.failed"}, output(rejected)
    assert "[b]" in output(rejected)
    assert "[a]" not in output(rejected)


def test_a02_a_covered_python_change_cannot_compensate_for_php(tmp_path: Path) -> None:
    project = bootstrapped(create_project(tmp_path / "project", component("app"), php("shop")))
    tests = project.path / "app/tests/test_app.py"
    project.write("app/tests/test_app.py", tests.read_text() + "    assert sign(0) == 1\n")
    python_only = project.commit("test the Python component more")
    assert python_only.returncode == 0, output(python_only)
    assert "unit coverage of shop" not in output(python_only)
    project.write("app/tests/test_app.py", tests.read_text() + "    assert sign(1) == 1\n")
    project.write("shop/src/Unused.php", UNUSED.format(namespace="App"))
    rejected = project.commit("add an uncovered PHP class")
    assert rejected.returncode != 0
    assert "coverage.new-file" in rules_of(rejected), output(rejected)
    assert "[shop]" in output(rejected)
    assert "[app]" not in output(rejected)


def test_every_autoload_root_is_measured(tmp_path: Path) -> None:
    spec = replace(php("shop"), source=("src", "lib"))
    project = create_project(tmp_path / "project", spec)
    autoload: JsonValue = {"psr-4": {"App\\": "src/", "Words\\": "lib/"}}
    project.write("shop/composer.json", manifest(autoload=autoload))
    project.write("shop/lib/Shout.php", WORDS)
    project.write("shop/tests/ShoutTest.php", WORDS_TEST)
    project.repo.commit_all("a second autoload root")
    bootstrapped(project)
    accepted = project.quality("check", "--all")
    assert accepted.returncode == 0, output(accepted)
    assert "unit coverage of shop: line 100.00% (4/4)" in output(accepted)
    project.write("shop/lib/Unused.php", UNUSED.format(namespace="Words"))
    rejected = project.commit("add a class nothing uses to the second root")
    assert rejected.returncode != 0
    assert "coverage.new-file" in rules_of(rejected), output(rejected)
    assert "new file 'shop/lib/Unused.php' has no unit coverage" in output(rejected)


def test_a_manifest_that_maps_a_prefix_outside_the_repository_is_rejected(shop: Project) -> None:
    document = json.loads((shop.path / "shop/composer.json").read_text())
    document["autoload"]["psr-4"]["Outside\\"] = "../../outside/"
    shop.write("shop/composer.json", json.dumps(document, indent=4) + "\n")
    result = shop.commit("map a prefix outside the repository", "shop/composer.json")
    assert result.returncode != 0
    assert rules_of(result) == {"php.config"}, output(result)
    assert "outside the repository" in output(result)


def test_one_line_methods_are_measured_by_their_statements(shop: Project) -> None:
    shop.write("shop/src/Sign.php", with_method(CORE, ONE_LINE))
    shop.write("shop/tests/SignTest.php", with_method(TESTS, ONE_LINE_TEST))
    result = shop.commit("add one-line methods")
    assert result.returncode != 0
    assert rules_of(result) == {"coverage.changed-lines", "php.format"}, output(result)
    assert "changed lines 50.00% (1/2)" in output(result)
    assert "uncovered: shop/src/Sign.php:19 " in output(result)


def test_a_script_no_test_loads_is_unmeasured_until_a_test_loads_it(shop: Project) -> None:
    shop.write("shop/src/greet.php", SCRIPT)
    rejected = shop.commit("add a script")
    assert rejected.returncode != 0
    assert "coverage.branch-unmeasured" in rules_of(rejected), output(rejected)
    assert "did not measure the branches of 'shop/src/greet.php'" in output(rejected)
    shop.write("shop/tests/GreetTest.php", SCRIPT_TEST)
    accepted = shop.commit("load the script in a test")
    assert accepted.returncode == 0, output(accepted)
    assert "unit coverage of shop: line 100.00% (5/5)" in output(accepted)


def test_coverage_ignore_markers_hide_no_code(shop: Project) -> None:
    shop.write("shop/src/Sign.php", with_method(CORE, IGNORED))
    result = shop.commit("ignore a method's coverage")
    assert result.returncode != 0
    assert {"suppressions.inline", "coverage.changed-lines"} <= rules_of(result), output(result)
    assert "changed lines 0.00% (0/1)" in output(result)
