"""Locate RL00 experiment prerequisites without launching or installing anything.

Bootstrap fills package caches, not persistent component installs. The caller must
materialize the locked Node, Dart and PHP trees offline under the caller-supplied
scratch root before resolving them. Native versions and extension availability need a later,
independently bounded runtime probe; path and package metadata are not such proof.
"""

from __future__ import annotations

import json
import os
import shutil
import tomllib
from pathlib import Path
from typing import Any, cast

from tests.acceptance.rl00bc.rl00bc_errors import invalid


def _file(path: Path, *, executable: bool = False) -> Path:
    if not path.is_file() or (executable and not os.access(path, os.X_OK)):
        invalid(f"missing {'executable' if executable else 'file'}: {path}")
    # Do not resolve the venv interpreter symlink: Python needs its venv path.
    return path.absolute()


def _json(path: Path) -> Any:
    return json.loads(_file(path).read_text(encoding="utf-8"))


def _tool(cache: Path, manifest: dict[str, Any], name: str) -> Path:
    entry = manifest["tools"][name]
    return _file(
        cache
        / "toolchains"
        / f"{name}-{entry['version']}"
        / entry.get("executable", entry["binary"]),
        executable=True,
    )


def _node_modules(repo: Path, prepared: Path) -> Path:
    lock = _json(repo / "tools/quality/src/quality/testkit/browserseed/package-lock.json")
    modules = prepared / "node/node_modules"
    for name in (
        "vitest",
        "@vitest/coverage-v8",
        "@playwright/test",
        "playwright",
        "playwright-core",
        "vite",
    ):
        expected = lock["packages"][f"node_modules/{name}"]["version"]
        actual = _json(modules / name / "package.json").get("version")
        if actual != expected:
            invalid(f"{name} installed version {actual!r} differs from lock {expected!r}")
    for name in ("vitest/vitest.mjs", "@playwright/test/cli.js", "vite/bin/vite.js"):
        _file(modules / name)
    return modules.absolute()


def _dart_config(repo: Path, prepared: Path) -> Path:
    path = _file(prepared / "dart/.dart_tool/package_config.json")
    data = _json(path)
    packages = cast("object", data.get("packages"))
    if not isinstance(packages, list):
        invalid(f"Dart test package missing from {path}")
    entries = cast("list[object]", packages)
    if not any(
        isinstance(p, dict) and cast("dict[str, object]", p).get("name") == "test" for p in entries
    ):
        invalid(f"Dart test package missing from {path}")
    # Verify the prepared lock is the helper lock, without claiming runtime version.
    lock = _file(repo / "tools/quality/helpers/dart/pubspec.lock")
    if _file(prepared / "dart/pubspec.lock").read_bytes() != lock.read_bytes():
        invalid("prepared Dart lock differs from helper lock")
    return path


def _php_files(repo: Path, prepared: Path) -> tuple[Path, Path]:
    source = _file(repo / "tools/quality/helpers/php/composer.lock")
    if _file(prepared / "php/composer.lock").read_bytes() != source.read_bytes():
        invalid("prepared PHP lock differs from helper lock")
    lock = _json(source)
    installed: object = _json(prepared / "php/vendor/composer/installed.json")
    if isinstance(installed, dict):
        mapping = cast("dict[str, object]", installed)
        installed = mapping.get("packages", mapping)
    entries = cast("list[dict[str, Any]]", installed)
    expected = [p["version"] for p in lock["packages-dev"] if p["name"] == "phpunit/phpunit"]
    actual = [p["version"] for p in entries if p["name"] == "phpunit/phpunit"]
    if len(expected) != 1 or actual != expected:
        invalid("installed PHPUnit does not match the helper lock")
    return (_file(prepared / "php/vendor/bin/phpunit"), _file(prepared / "php/vendor/autoload.php"))


def _context(repo: Path) -> tuple[Path, dict[str, Any], Path, Path]:
    core = repo / "tools/quality"
    manifest = tomllib.loads(_file(core / "toolchains.toml").read_text(encoding="utf-8"))
    cache_home = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    cache = Path(cache_home).absolute() / "quality"
    # This is the same fixed search order used by the PHP profile, not PATH.
    php = next(
        (
            p
            for p in (Path("/usr/local/bin/php"), Path("/usr/bin/php"), Path("/bin/php"))
            if p.is_file()
        ),
        None,
    )
    if php is None:
        invalid("system PHP missing from quality's fixed system directories")
    return core, manifest, cache, _file(php, executable=True)


def _prepare_materialization(core: Path, root: Path) -> tuple[Path, Path, Path, Path]:
    node_dir, dart_dir, php_dir = (root / name for name in ("node", "dart", "php"))
    for directory in (node_dir, dart_dir, php_dir, root / "home"):
        directory.mkdir(parents=True, exist_ok=True)
    browser_lock = core / "src/quality/testkit/browserseed/package-lock.json"
    lock = _json(browser_lock)
    package = lock["packages"][""]
    (node_dir / "package.json").write_text(json.dumps(package) + "\n", encoding="utf-8")
    shutil.copyfile(browser_lock, node_dir / "package-lock.json")
    for name in ("pubspec.yaml", "pubspec.lock"):
        shutil.copyfile(_file(core / "helpers/dart" / name), dart_dir / name)
    for name in ("composer.json", "composer.lock"):
        shutil.copyfile(_file(core / "helpers/php" / name), php_dir / name)
    (php_dir / "src").mkdir(exist_ok=True)
    (php_dir / "tests").mkdir(exist_ok=True)
    home = root / "home"
    npmrc, globalrc = home / "npmrc", home / "npmrc-global"
    npmrc.write_text("", encoding="utf-8")
    globalrc.write_text("", encoding="utf-8")
    return node_dir, dart_dir, php_dir, home


def _composer_command(
    php_dir: Path, php: Path, composer: Path, cache: Path, home: Path, env: dict[str, str]
) -> tuple[Path, list[str], dict[str, str]]:
    return (
        php_dir,
        [
            str(php),
            "-d",
            "display_errors=stderr",
            str(composer),
            "install",
            "--no-progress",
            "--no-scripts",
            "--no-plugins",
        ],
        {
            **env,
            "COMPOSER_HOME": str(home / "composer"),
            "COMPOSER_CACHE_DIR": str(cache / "composer"),
            "COMPOSER_NO_INTERACTION": "1",
            "COMPOSER_NO_AUDIT": "1",
            "COMPOSER_DISABLE_NETWORK": "1",
            "XDEBUG_MODE": "off",
        },
    )


def materialization(repo: Path, root: Path) -> list[tuple[Path, list[str], dict[str, str]]]:
    """Copy locked manifests and return offline commands; never execute commands.

    The caller runs these as measured preparation under its finite envelope.
    PHP and Xdebug are system-managed: probe their versions and whether Xdebug
    is already loaded separately before coverage; PHP may need
    ``-d zend_extension=xdebug``. No Xdebug state is inferred here.
    """
    repo, root = repo.absolute(), root.absolute()
    core, manifest, cache, php = _context(repo)
    node = _tool(cache, manifest, "node")
    dart = _tool(cache, manifest, "dart")
    composer = _tool(cache, manifest, "composer")
    node_dir, dart_dir, php_dir, home = _prepare_materialization(core, root)
    env = {"HOME": str(home), "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}
    npm = _file(node.parent.parent / "lib/node_modules/npm/bin/npm-cli.js")
    npmrc, globalrc = home / "npmrc", home / "npmrc-global"
    return [
        (
            node_dir,
            [
                str(node),
                str(npm),
                "ci",
                "--offline",
                "--ignore-scripts",
                "--include=dev",
                "--no-audit",
                "--no-fund",
                "--no-update-notifier",
                "--no-progress",
                "--loglevel=error",
                f"--cache={cache / 'npm'}",
                f"--userconfig={npmrc}",
                f"--globalconfig={globalrc}",
            ],
            {**env, "NODE_DISABLE_COMPILE_CACHE": "1"},
        ),
        (
            dart_dir,
            [str(dart), "--suppress-analytics", "pub", "get", "--offline", "--enforce-lockfile"],
            {**env, "PUB_CACHE": str(cache / "pub"), "DART_SUPPRESS_ANALYTICS": "true"},
        ),
        _composer_command(php_dir, php, composer, cache, home, env),
    ]


def resolve(repo: Path, root: Path) -> dict[str, str]:
    """Resolve known paths; missing prerequisites raise, and no command is run."""
    repo = repo.absolute()
    core, manifest, cache, php = _context(repo)
    prepared = root.absolute()
    python = _file(core / ".venv/bin/python", executable=True)
    phpunit, autoload = _php_files(repo, prepared)
    values = {
        "RL00_PYTHON": python,
        "RL00_CHILD_PYTHON": python,
        "RL00_DART": _tool(cache, manifest, "dart"),
        "RL00_DART_PACKAGE_CONFIG": _dart_config(repo, prepared),
        "RL00_NODE": _tool(cache, manifest, "node"),
        "RL00_NODE_MODULES": _node_modules(repo, prepared),
        "RL00_CHROMIUM": _tool(cache, manifest, "chromium"),
        "RL00_PHP": php,
        "RL00_PHPUNIT": phpunit,
        "RL00_PHP_AUTOLOAD": autoload,
    }
    return {key: str(value) for key, value in values.items()}
