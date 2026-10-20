"""Bounded readers for the native configuration files of a component."""

from __future__ import annotations

import json
import posixpath
import tomllib
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import cast

from quality.boundedio import ReportError, read_bounded

CONFIG_LIMIT = 4 * 1024 * 1024
MAX_EXTENDS = 5

type Table = Mapping[str, object]
# Records a problem: the file relative to the component directory, then the message.
type Report = Callable[[str, str], None]


def load_toml(path: Path) -> Table:
    """Read a bounded TOML file; raise ReportError when it is unusable."""
    data = read_bounded(path, CONFIG_LIMIT)
    try:
        return tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        msg = f"{path.name} is not valid TOML: {error}"
        raise ReportError(msg) from error


def load_json_object(path: Path) -> Table:
    """Read a bounded file holding one plain JSON object (no comments)."""
    data = read_bounded(path, CONFIG_LIMIT)
    try:
        value: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        msg = f"{path.name} is not plain JSON: {error}"
        raise ReportError(msg) from error
    if not isinstance(value, dict):
        msg = f"{path.name} does not hold a JSON object"
        raise ReportError(msg)
    return cast(Table, value)


def table(data: Table, *keys: str) -> Table | None:
    """Return the nested table at `keys`, or None when any level is missing."""
    current = data
    for key in keys:
        value = current.get(key)
        if not isinstance(value, Mapping):
            return None
        current = cast(Table, value)
    return current


def strings(value: object) -> list[str]:
    """Return the strings of a list setting; other values hold none."""
    items = cast(list[object], value) if isinstance(value, list) else []
    return [item for item in items if isinstance(item, str)]


def inside(base: Path, value: str, snapshot: Path) -> bool:
    """Whether a relative path setting resolves inside the snapshot.

    Tools expand `~` and environment variables in some settings, so values that
    use them are treated as pointing outside.
    """
    if PurePosixPath(value).is_absolute() or value.startswith("~") or "$" in value:
        return False
    return (base / value).resolve().is_relative_to(snapshot.resolve())


def label(path: Path, directory: Path) -> str:
    """Name a configuration file relative to the component directory."""
    relative = posixpath.relpath(path.resolve().as_posix(), directory.resolve().as_posix())
    return posixpath.normpath(relative)
