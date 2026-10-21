"""Bounded readers for the native configuration files of a component."""

from __future__ import annotations

import json
import posixpath
import tomllib
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import cast

import yaml

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


def _repeated_in(node: yaml.Node) -> str | None:
    """Return a key that a mapping node repeats, if it is a mapping and repeats one."""
    if not isinstance(node, yaml.MappingNode):
        return None
    keys = [key.value for key, _ in node.value if isinstance(key, yaml.ScalarNode)]
    return next((str(key) for index, key in enumerate(keys) if key in keys[:index]), None)


def _children(node: yaml.Node) -> list[yaml.Node]:
    if isinstance(node, yaml.MappingNode):
        return [item for pair in node.value for item in pair]
    if isinstance(node, yaml.SequenceNode):
        return list(node.value)
    return []


def _repeated_key(root: yaml.Node | None) -> str | None:
    """Return a key that some mapping of the document repeats; Dart's YAML parser refuses those.

    Aliases make the document a graph, possibly a cyclic one, so each node is visited once.
    """
    pending = [root] if root is not None else []
    seen: set[int] = set()
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        repeated = _repeated_in(node)
        if repeated is not None:
            return repeated
        pending.extend(_children(node))
    return None


def load_yaml_mapping(path: Path) -> Table:
    """Read a bounded YAML file holding one mapping, with no mapping that repeats a key."""
    data = read_bounded(path, CONFIG_LIMIT)
    try:
        text = data.decode("utf-8")
        loader = yaml.SafeLoader(text)
        try:
            repeated = _repeated_key(loader.get_single_node())
        finally:
            loader.dispose()
        value: object = yaml.safe_load(text)
    except (UnicodeDecodeError, yaml.YAMLError, RecursionError) as error:
        msg = f"{path.name} is not valid YAML: {error}"
        raise ReportError(msg) from error
    if repeated is not None:
        msg = f"{path.name} repeats the key '{repeated}'"
        raise ReportError(msg)
    if not isinstance(value, dict):
        msg = f"{path.name} does not hold a YAML mapping"
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
