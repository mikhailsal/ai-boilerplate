"""Retain the helper's locked Dart dependency graph in a native trial root."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import cast
from urllib.parse import urljoin

from tests.acceptance.rl00bc.rl00bc_errors import invalid


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        invalid("invalid Dart dependency configuration")
    return cast(dict[str, object], value)


def _package(value: object, source: Path, root: Path, name: str) -> dict[str, object]:
    package = _object(value)
    uri = package.get("rootUri")
    if not isinstance(uri, str) or not isinstance(package.get("name"), str):
        invalid("invalid Dart package identity or root")
    absolute = root.as_uri() + "/" if package["name"] == name else urljoin(source.as_uri(), uri)
    return {**package, "rootUri": absolute}


def prepare(repo: Path, root: Path, config: Path) -> None:
    """Copy matching manifests before the package configuration to avoid resolution drift."""
    helper = repo / "tools/quality/helpers/dart"
    source = (helper / "pubspec.yaml").read_text(encoding="utf-8")
    match = re.search(r"(?m)^name:\s*([A-Za-z0-9_]+)\s*$", source)
    if match is None:
        invalid("Dart helper manifest has no package name")
    for name in ("pubspec.yaml", "pubspec.lock"):
        shutil.copyfile(helper / name, root / name)
    package_dir = root / ".dart_tool"
    package_dir.mkdir(exist_ok=True)
    graph = config.with_name("package_graph.json")
    if graph.is_file():
        shutil.copyfile(graph, package_dir / graph.name)
    data = _object(json.loads(config.read_text(encoding="utf-8")))
    entries = data.get("packages")
    if not isinstance(entries, list):
        invalid("Dart package configuration has no packages")
    data["packages"] = [_package(value, config, root, match.group(1))
                        for value in cast(list[object], entries)]
    (package_dir / "package_config.json").write_text(json.dumps(data), encoding="utf-8")
