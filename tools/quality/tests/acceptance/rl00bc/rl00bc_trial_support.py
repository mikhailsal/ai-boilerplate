"""One bounded native trial for the unrun RL00b/c research harness.

Provider materialization is controller-side and timed separately; every native
command, including the browser build, runs inside the same protected leaf.
This module neither provisions a leaf nor caches a resource verdict.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from tests.acceptance.rl00bc import (
    rl00bc_dart,
    rl00bc_node,
    rl00bc_php,
    rl00bc_python,
)
from tests.acceptance.rl00bc.rl00bc_errors import invalid

LIMIT = 65536
RESERVE_NS = 3_000_000_000
PATH_KEYS = frozenset(
    {
        "RL00_PYTHON",
        "RL00_CHILD_PYTHON",
        "RL00_PHP",
        "RL00_PHPUNIT",
        "RL00_PHP_AUTOLOAD",
        "RL00_XDEBUG_LOADED",
        "RL00_NODE",
        "RL00_NODE_MODULES",
        "RL00_CHROMIUM",
        "RL00_DART",
        "RL00_DART_PACKAGE_CONFIG",
        "RL00_SLOW_SECONDS",
    }
)


class Provider(Protocol):
    def prepare(self, root: Path, repo: Path, profile: str) -> None: ...

    def command(
        self,
        root: Path,
        repo: Path,
        output: Path,
        selected: str | None,
        *,
        profile: str,
        workers: int,
        coverage: bool,
    ) -> list[str]: ...

    def results(self, root: Path, output: Path, *, profile: str) -> list[dict[str, object]]: ...


PROVIDERS: dict[str, Provider] = {
    "python": rl00bc_python,
    "php": rl00bc_php,
    "node": rl00bc_node,
    "browser": rl00bc_node,
    "dart": rl00bc_dart,
}
STRICT: dict[str, tuple[int, int, float]] = {
    "python": (384, 128, 5.0),
    "php": (384, 128, 5.0),
    "node": (768, 128, 5.0),
    "dart": (1024, 128, 5.0),
    "browser": (1536, 256, 12.0),
}


def _save(path: Path, value: object) -> bytes:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > LIMIT:
        invalid(f"bounded experiment record exceeds {LIMIT} bytes")
    path.write_bytes(data)
    return data


def _valid_environment_value(value: object) -> bool:
    return isinstance(value, str) and len(value) <= 4096 and "\0" not in value


def _validate_corpus(size: str, mode: str, allocation_mib: int, shared_mib: int) -> None:
    if size not in {"small", "large"} or mode not in {"correctness", "performance"}:
        invalid("invalid corpus configuration")
    if not 1 <= allocation_mib <= 1536 or not 0 <= shared_mib <= 128:
        invalid("invalid finite allocation")


def _validate_environment(
    environment: dict[str, str], size: str, mode: str, target: str,
    allocation_mib: int, shared_mib: int,
) -> None:
    unknown = set(environment) - PATH_KEYS
    if unknown:
        invalid(f"unsupported environment keys: {sorted(unknown)}")
    _validate_corpus(size, mode, allocation_mib, shared_mib)
    if len(target) > 128 or any(
        ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for ch in target
    ):
        invalid("invalid target label")
    if any(not _valid_environment_value(v) for v in environment.values()):
        invalid("invalid environment value")


def _search_path(environment: dict[str, str]) -> str:
    tool_dirs: list[str] = []
    for key in ("RL00_NODE", "RL00_PYTHON"):
        if key in environment:
            executable = Path(environment[key])
            if not executable.is_absolute() or not executable.is_file():
                invalid(f"{key} must name an absolute executable file")
            directory = str(executable.parent)
            if directory not in tool_dirs:
                tool_dirs.append(directory)
    return ":".join([*tool_dirs, "/usr/local/bin", "/usr/bin", "/bin"])


def _environment(
    environment: dict[str, str],
    root: Path,
    output: Path,
    *,
    size: str,
    mode: str,
    target: str,
    allocation_mib: int,
    shared_mib: int,
    instrument: bool,
    coverage: bool,
) -> dict[str, str]:
    _validate_environment(environment, size, mode, target, allocation_mib, shared_mib)
    home = root / "home"
    temporary = root / "tmp"
    events = output / "events"
    for directory in (home, temporary, events):
        directory.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": _search_path(environment),
        "HOME": str(home),
        "TMPDIR": str(temporary),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "CI": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "XDEBUG_MODE": "coverage" if coverage else "off",
        **environment,
        "RL00_MODE": mode,
        "RL00_SIZE": size,
        "RL00_TARGET": target,
        "RL00_ALLOC_MIB": str(allocation_mib),
        "RL00_SHARED_MIB": str(shared_mib),
        "RL00_INSTRUMENT": "1" if instrument else "0",
        "RL00_EVENT_DIR": str(events),
    }


def _rl00_environment(environment: Mapping[str, str]) -> dict[str, str]:
    return {key: value for key, value in environment.items() if key.startswith("RL00_")}


def _restore_environment(keys: set[str], previous: dict[str, str | None]) -> None:
    for key in keys:
        os.environ.pop(key, None)
    os.environ.update({key: value for key, value in previous.items() if value is not None})


def _provider_commands(
    provider: Provider,
    root: Path,
    repo: Path,
    output: Path,
    profile: str,
    selected: str | None,
    workers: int,
    coverage: bool,
    env: dict[str, str],
) -> list[str]:
    # Providers read process environment; caller must serialize this preparation.
    selected_env = _rl00_environment(env)
    keys = set(_rl00_environment(os.environ)) | set(selected_env)
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        os.environ.update(selected_env)
        provider.prepare(root, repo, profile)
        return provider.command(
            root, repo, output, selected, profile=profile, workers=workers, coverage=coverage
        )
    finally:
        _restore_environment(keys, previous)


