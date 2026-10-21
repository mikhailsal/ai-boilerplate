"""A08 for PHP: a machine without Xdebug cannot satisfy the branch gate (decision 0013).

Each case gives the project a launcher whose system PHP is a wrapper: the
system `php` with an extension directory that holds every installed extension
but Xdebug, as on a machine without the Xdebug package, with PCOV loaded or
not. The launcher injects the wrapper where the core locates the system PHP;
the core reads no setting that could. PCOV is a prerequisite of this suite
(decision 0002), so that a PCOV-only machine is a real one.
"""

import shlex
import sys
from pathlib import Path

from quality.adapters.php.runtime import system_php
from quality.process import Command, run
from quality.testkit.nodefakes import script
from quality.testkit.phpproject import CORE, TESTS
from quality.testkit.scratch import CORE_SOURCE, Project, output

LAUNCHER = """\
import sys
from pathlib import Path

sys.path.insert(0, sys.argv.pop(1))
php = Path(sys.argv.pop(1))
sys.argv[0] = "quality"
from quality.adapters.php import runtime

runtime.system_php = lambda: php
from quality.cli.main import main

raise SystemExit(main())
"""
# The gate probes PHP with `-r`; this wrapper answers as a PHP with Xdebug 3.5 would.
CLAIMS_XDEBUG = """\
case " $* " in
*" -r "*) printf '{{"php": "{version}", "xdebug": "3.5.0"}}'; exit 0 ;;
esac
"""
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
MISSING = "Xdebug is not available to {php}; branch coverage needs it, which PCOV and phpdbg"
REFUSED = "No code coverage driver available that supports line and branch coverage"


def answer(php: Path, code: str) -> str:
    """Return what the system PHP prints for `code`."""
    completed = run(Command((str(php), "-r", code), cwd=Path("/"), timeout=60.0))
    assert completed.returncode == 0, completed.stderr_text()
    return completed.stdout_text()


def without_xdebug(directory: Path, *, pcov: bool, claims_xdebug: bool = False) -> Path:
    """Write a system PHP without Xdebug, with PCOV when `pcov`; return its path."""
    real = system_php()
    installed = Path(answer(real, 'echo ini_get("extension_dir");'))
    extensions = directory / "extensions"
    extensions.mkdir(parents=True)
    for library in installed.glob("*.so"):
        if library.name != "xdebug.so":
            (extensions / library.name).symlink_to(library)
    assert (extensions / "pcov.so").exists(), "this suite needs PCOV (decision 0002)"
    flags = ["-d", f"extension_dir={extensions}"]
    if pcov:
        flags += ["-d", "extension=pcov", "-d", "pcov.enabled=1"]
    probe = CLAIMS_XDEBUG.format(version=answer(real, "echo PHP_VERSION;")) if claims_xdebug else ""
    body = f'{probe}exec {shlex.join([str(real), *flags])} "$@"\n'
    return script(directory / "bin" / "php", body)


def launch_with(project: Project, php: Path) -> None:
    """Make the project's unstaged launcher run the core with `php` as the system PHP."""
    argv = (sys.executable, "-I", "-c", LAUNCHER, str(CORE_SOURCE), str(php))
    project.repo.write("quality", f'#!/bin/sh\nexec {shlex.join(argv)} "$@"\n', executable=True)


def add_twice(project: Project) -> None:
    """Stage a covered change, leaving the launcher unstaged."""
    project.write("shop/src/Sign.php", CORE.removesuffix("}\n") + TWICE + "}\n")
    project.write("shop/tests/SignTest.php", TESTS.removesuffix("}\n") + TWICE_TEST + "}\n")
    project.repo.git("add", "shop")


def test_a08_a_php_without_any_coverage_driver_cannot_run_the_gate(shop: Project) -> None:
    php = without_xdebug(shop.path.parent / "no-driver", pcov=False)
    launch_with(shop, php)
    add_twice(shop)
    before = shop.head()
    rejected = shop.git("commit", "-q", "-m", "add twice")
    assert rejected.returncode != 0
    assert MISSING.format(php=php) in output(rejected)
    assert "unit coverage of shop" not in output(rejected)
    assert shop.head() == before
    doctor = shop.quality("doctor")
    assert doctor.returncode != 0
    assert MISSING.format(php=php) in output(doctor)
    shop.repo.git("checkout", "--", "quality")
    accepted = shop.git("commit", "-q", "-m", "add twice")
    assert accepted.returncode == 0, output(accepted)


def test_a08_a_php_with_only_pcov_cannot_run_the_gate(shop: Project) -> None:
    php = without_xdebug(shop.path.parent / "pcov", pcov=True)
    assert answer(php, 'echo phpversion("pcov") ?: "none";') != "none"
    launch_with(shop, php)
    add_twice(shop)
    rejected = shop.git("commit", "-q", "-m", "add twice")
    assert rejected.returncode != 0
    assert MISSING.format(php=php) in output(rejected)
    assert "unit coverage of shop" not in output(rejected)


def test_a08_pcov_cannot_measure_branches_even_when_php_claims_xdebug(shop: Project) -> None:
    php = without_xdebug(shop.path.parent / "claims", pcov=True, claims_xdebug=True)
    launch_with(shop, php)
    add_twice(shop)
    rejected = shop.git("commit", "-q", "-m", "add twice")
    assert rejected.returncode != 0
    assert REFUSED in output(rejected)
    assert "unit coverage of shop" not in output(rejected)
