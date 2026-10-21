"""R03.8 and A10 in a PHP component: the configuration the gate checks and ignores.

The gate validates composer.json and composer.lock before any tool runs and
never reads the component's own settings for PHP CS Fixer, PHPStan, and
PHPUnit; a change to either manifest reruns the component (decision 0013).
"""

import json

from quality.testkit.phpproject import TYPED, lockfile
from quality.testkit.scratch import Project, output, rules_of

SOURCE = "shop/src/Sign.php"


def test_the_components_own_tool_settings_do_not_change_the_verdict(shop: Project) -> None:
    marker = shop.path.parent / "executed"
    shop.write(SOURCE, TYPED)
    shop.write(
        "shop/phpstan.neon", "parameters:\n    level: 0\n    ignoreErrors:\n        - '#.*#'\n"
    )
    shop.write(
        "shop/phpunit.xml",
        '<?xml version="1.0"?>\n<phpunit><source><exclude><directory>src</directory>'
        "</exclude></source></phpunit>\n",
    )
    shop.write(
        "shop/.php-cs-fixer.php",
        f"<?php\n\nfile_put_contents('{marker}', 'executed');\n\n"
        "return (new PhpCsFixer\\Config())->setRules([]);\n",
    )
    result = shop.commit("weaken the tools")
    assert result.returncode != 0
    assert rules_of(result) == {"php.types"}, output(result)
    assert "unit coverage of shop: line 100.00% (3/3), branch 100.00% (3/3)" in output(result)
    assert not marker.exists()


def test_a08_a_component_that_locks_another_test_runner_fails(shop: Project) -> None:
    document = json.loads(lockfile())
    for entry in document["packages-dev"]:
        if entry["name"] == "phpunit/phpunit":
            entry["version"] = "13.4.2"
    shop.write("shop/composer.lock", json.dumps(document, indent=4) + "\n")
    result = shop.commit("lock another PHPUnit", "shop/composer.lock")
    assert result.returncode != 0
    assert rules_of(result) == {"php.config"}, output(result)
    assert "phpunit/phpunit is locked at '13.4.2'" in output(result)
    assert "unit coverage of shop" not in output(result)


def test_a_committed_vendor_directory_is_rejected(shop: Project) -> None:
    shop.write("shop/vendor/autoload.php", "<?php\n")
    shop.repo.git("add", "-f", "shop/vendor/autoload.php")
    result = shop.git("commit", "-q", "-m", "commit the installed packages")
    assert result.returncode != 0
    assert "php.config" in rules_of(result), output(result)
    assert "`vendor/` is committed" in output(result)


def test_a10_a_manifest_change_reruns_the_component(shop: Project) -> None:
    manifest = json.loads((shop.path / "shop/composer.json").read_text())
    manifest["config"] = {"vendor-dir": "lib"}
    shop.write("shop/composer.json", json.dumps(manifest, indent=4) + "\n")
    result = shop.commit("move the vendor directory", "shop/composer.json")
    assert result.returncode != 0
    assert rules_of(result) == {"php.config"}, output(result)
    assert "`config.vendor-dir` is 'lib'" in output(result)


def test_a10_a_lockfile_change_reruns_the_suites(shop: Project) -> None:
    shop.write("shop/composer.lock", lockfile() + "\n")
    result = shop.commit("touch the lockfile", "shop/composer.lock")
    assert result.returncode == 0, output(result)
    assert "unit coverage of shop: line 100.00%" in output(result)
