"""Probe actual pinned runtimes in finite native leaves before collecting evidence."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urljoin, urlsplit

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_kernel
from tests.acceptance.rl00bc.rl00bc_errors import invalid

VERSION = re.compile(r"(?<![0-9])([0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?)(?![0-9.])")
PHP_CODE = 'echo json_encode(["php" => PHP_VERSION, "xdebug" => phpversion("xdebug") ?: null]);'
PYTHON_CODE = (
    "import importlib.metadata as m,json,sys; "
    "print(json.dumps({'python':'.'.join(map(str,sys.version_info[:3])),"
    "'pytest':m.version('pytest'),'coverage':m.version('coverage')}))"
)


def _version(text: str) -> str:
    match = VERSION.search(text)
    if match is None:
        invalid("runtime did not report a complete version")
    return match.group(1)


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        invalid("runtime probe returned invalid JSON object")
    return cast(dict[str, object], value)


def _string(value: object) -> str:
    if not isinstance(value, str) or not value:
        invalid("runtime probe returned an invalid version")
    return value


def _pin(value: object, expected: str, name: str) -> str:
    actual = _string(value)
    if actual != expected:
        invalid(f"{name} version {actual!r} differs from pinned {expected!r}")
    return actual


def _minor(value: object, expected: str, name: str) -> str:
    actual = _string(value)
    if ".".join(actual.split(".")[:2]) != expected:
        invalid(f"{name} version {actual!r} differs from supported minor {expected!r}")
    return actual


def _nested(data: dict[str, object], *keys: str) -> object:
    value: object = data
    for key in keys:
        value = _object(value)[key]
    return value


def _dependency(project: dict[str, object], name: str) -> str:
    group = _nested(project, "dependency-groups", "dev")
    if not isinstance(group, list):
        invalid("missing Python development dependency pins")
    prefix = name + "=="
    pins = [value.removeprefix(prefix) for value in cast(list[object], group)
            if isinstance(value, str) and value.startswith(prefix)]
    if len(pins) != 1:
        invalid(f"missing or ambiguous {name} version pin")
    return pins[0]


@dataclass
class _Prober:
    work: Group
    repo: Path
    output: Path
    environment: dict[str, str]
    ancestor_deadline_ns: int
    manifest: dict[str, object]
    project: dict[str, object]
    records: dict[str, object] = field(default_factory=dict[str, object])
    versions: dict[str, str] = field(default_factory=dict[str, str])
    xdebug_loaded: bool = False

    def path(self, name: str) -> Path:
        value = self.environment.get(name, "")
        path = Path(value)
        if not value or not path.is_absolute() or not path.is_file():
            invalid(f"{name} must name an existing absolute runtime file")
        return path

    def run(self, name: str, argv: list[str]) -> str:
        directory = self.output / name
        env = {
            "HOME": str(self.output / "home"), "TMPDIR": str(self.output / "tmp"),
            "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "XDEBUG_MODE": "off",
        }
        kernel = rl00bc_kernel.execute(
            self.work, argv, self.repo, env, directory, memory_mib=512, tasks=64,
            native_seconds=20, ancestor_deadline_ns=self.ancestor_deadline_ns,
        )
        self.records[name] = {
            "argv": argv, "kernel": kernel, "kernel_record": str(directory / "result.json"),
            "stdout": str(directory / "stdout.log"), "stderr": str(directory / "stderr.log"),
        }
        if not kernel.get("success") or not kernel.get("cleanup_complete"):
            invalid(f"{name} runtime probe failed")
        truncated = _object(kernel.get("truncated"))
        if truncated.get("stdout") or truncated.get("stderr"):
            invalid(f"{name} runtime output was truncated")
        stdout = (directory / "stdout.log").read_text(encoding="utf-8")
        return stdout or (directory / "stderr.log").read_text(encoding="utf-8")

    def pinned(self, name: str, key: str, argv: list[str]) -> None:
        expected = _string(_nested(self.manifest, "tools", key, "version"))
        self.versions[name] = _pin(_version(self.run(name, argv)), expected, name)

    def python(self) -> None:
        argv = [str(self.path("RL00_PYTHON")), "-c", PYTHON_CODE]
        value = _object(json.loads(self.run("python", argv)))
        requirement = _string(_nested(self.project, "project", "requires-python"))
        match = re.fullmatch(r">=([0-9]+\.[0-9]+),<([0-9]+\.[0-9]+)", requirement)
        if match is None:
            invalid("unsupported Python version requirement")
        self.versions["python"] = _minor(value.get("python"), match.group(1), "python")
        for name in ("pytest", "coverage"):
            self.versions[name] = _pin(value.get(name), _dependency(self.project, name), name)

    def php(self) -> None:
        php = str(self.path("RL00_PHP"))
        argv = [php, "-d", "display_errors=stderr", "-r", PHP_CODE]
        initial = _object(json.loads(self.run("php", argv)))
        self.xdebug_loaded = initial.get("xdebug") is not None
        measured = initial
        if not self.xdebug_loaded:
            measured = _object(json.loads(self.run(
                "php-xdebug", [php, "-d", "display_errors=stderr", "-d", "zend_extension=xdebug",
                               "-r", PHP_CODE]
            )))
        for name in ("php", "xdebug"):
            expected = _string(_nested(self.manifest, "runtimes", name, "version"))
            self.versions[name] = _minor(measured.get(name), expected, name)
        if measured.get("php") != initial.get("php"):
            invalid("PHP runtime changed while probing Xdebug")
        unit = self.run("phpunit", [php, str(self.path("RL00_PHPUNIT")), "--version"])
        expected = _string(_nested(self.manifest, "packages", "composer", "phpunit/phpunit"))
        self.versions["phpunit"] = _pin(_version(unit), expected, "phpunit")

    def dart_packages(self) -> None:
        config = self.path("RL00_DART_PACKAGE_CONFIG")
        data = _object(json.loads(config.read_text(encoding="utf-8")))
        entries = data.get("packages")
        if not isinstance(entries, list):
            invalid("invalid prepared Dart package configuration")
        packages = [_object(value) for value in cast(list[object], entries)]
        for name in ("test", "coverage"):
            matches = [item for item in packages if item.get("name") == name]
            if len(matches) != 1:
                invalid(f"prepared Dart package {name} is missing or ambiguous")
            uri = urlsplit(urljoin(config.as_uri(), _string(matches[0].get("rootUri"))))
            if uri.scheme != "file" or uri.netloc:
                invalid(f"prepared Dart package {name} has a nonlocal root")
            pubspec = Path(unquote(uri.path)) / "pubspec.yaml"
            source = pubspec.read_text(encoding="utf-8")
            match = re.search(r"(?m)^version:\s*['\"]?([^\s'\"]+)", source)
            if match is None:
                invalid(f"prepared Dart package {name} has no version")
            expected = _string(_nested(self.manifest, "packages", "pub", name))
            self.versions[f"dart-{name}"] = _pin(match.group(1), expected, f"dart-{name}")
            self.records[f"dart-{name}"] = {"package_config": str(config), "pubspec": str(pubspec)}

    def node_packages(self) -> None:
        node = str(self.path("RL00_NODE"))
        modules = Path(self.environment.get("RL00_NODE_MODULES", ""))
        if not modules.is_absolute() or not modules.is_dir():
            invalid("RL00_NODE_MODULES must name the prepared absolute directory")
        commands = (
            ("vitest", modules / "vitest/vitest.mjs", "npm", "vitest"),
            ("playwright", modules / "@playwright/test/cli.js", "npm-browser", "@playwright/test"),
            ("vite", modules / "vite/bin/vite.js", "npm-browser", "vite"),
        )
        for name, script, group, package in commands:
            expected = _string(_nested(self.manifest, "packages", group, package))
            self.versions[name] = _pin(_version(self.run(name, [node, str(script), "--version"])),
                                       expected, name)

    def collect(self) -> None:
        self.python()
        for name, key in (("node", "RL00_NODE"), ("dart", "RL00_DART"),
                          ("chromium", "RL00_CHROMIUM")):
            self.pinned(name, name, [str(self.path(key)), "--version"])
        self.dart_packages()
        self.php()
        self.node_packages()


def probe(
    work: Group, repo: Path, output: Path, environment: dict[str, str], *,
    ancestor_deadline_ns: int,
) -> dict[str, object]:
    """Record actual runtime versions and bounded process evidence; failures are setup nonpasses."""
    repo, output = repo.absolute(), output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    (output / "home").mkdir()
    (output / "tmp").mkdir()
    result: dict[str, object] = {"status": "setup-nonpass", "bindings": dict(environment)}
    try:
        manifest_path = repo / "tools/quality/toolchains.toml"
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        project = tomllib.loads((repo / "tools/quality/pyproject.toml").read_text(encoding="utf-8"))
        runner = _Prober(work, repo, output, environment, ancestor_deadline_ns, manifest, project)
        result.update({"probes": runner.records, "versions": runner.versions})
        runner.collect()
        result["xdebug_loaded"] = runner.xdebug_loaded
        result["status"] = "verified"
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        result["error"] = f"{type(error).__name__}: {error}"[:1024]
    (output / "runtime.json").write_text(
        json.dumps(result, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
