"""The TypeScript helper: the compiler API and ESLint, run by the pinned Node (decision 0011).

The helper is a TypeScript program in `tools/quality/helpers/typescript` that
Node runs directly, located relative to this package so a materialized
candidate core uses its own helper. It has no dependencies of its own: it loads
`typescript` and `eslint` the way Node resolves them from the component
directory, so the versions the component locks do the work. A request is a
JSON file; the response is one JSON object on stdout that carries the protocol
version. Exit status 2 is a request the helper cannot serve and 1 an
unexpected failure; both are tool failures, as is any field of an unexpected
type.
"""

from __future__ import annotations

import json
import posixpath
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

from quality.adapters.native import fail, run_tool
from quality.adapters.typescript.environment import Node
from quality.boundedio import JsonValue, ReportError, parse_json
from quality.process import Command

# src/quality/adapters/typescript/helper.py -> tools/quality
CORE = Path(__file__).resolve().parents[4]
HELPER = CORE / "helpers" / "typescript" / "src" / "main.ts"
PROTOCOL = 1
TIMEOUT = 1800.0
TOOL = "typescript helper"

type Entry = Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Program:
    """The helper script and the pinned Node that runs it."""

    node: Node
    path: Path = HELPER


def run_helper(
    program: Program, command: str, request: Mapping[str, JsonValue], *, work: Path, cwd: Path
) -> Entry:
    """Run one helper command and return its checked response."""
    if not program.path.is_file():
        fail(TOOL, f"the helper is missing at {program.path}")
    requests = work / "typescript-requests"
    requests.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=requests, prefix=f"{command}-", suffix=".json", delete=False
    ) as handle:
        json.dump({"protocol": PROTOCOL, **request}, handle)
    argv = (str(program.node.executable), str(program.path), command, handle.name)
    env = program.node.environ(work / "typescript-home" / "helper")
    completed = run_tool(Command(argv, cwd=cwd, timeout=TIMEOUT, env=env), name=TOOL, accepted={0})
    try:
        response = parse_json(completed.stdout, f"{TOOL} {command} output")
    except ReportError as error:
        fail(TOOL, str(error))
    if not isinstance(response, dict) or response.get("protocol") != PROTOCOL:
        fail(TOOL, f"{command} answered without protocol {PROTOCOL}")
    return response


def repository_path(snapshot: Path, name: str) -> str | None:
    """Return the repository path of an absolute file name, or None outside the snapshot."""
    path = PurePosixPath(posixpath.normpath(name))
    for root in (snapshot, snapshot.resolve()):
        base = PurePosixPath(root.as_posix())
        if path.is_absolute() and path.is_relative_to(base) and path != base:
            return path.relative_to(base).as_posix()
    return None


def entries(value: Entry, key: str) -> list[Entry]:
    """Return a list of objects, or fail."""
    found = value.get(key)
    if not isinstance(found, list) or not all(isinstance(item, dict) for item in found):
        fail(TOOL, f"'{key}' is not a list of objects")
    return cast(list[Entry], found)


def text(value: Entry, key: str) -> str:
    """Return a string field, or fail."""
    found = value.get(key)
    if not isinstance(found, str):
        fail(TOOL, f"'{key}' is not a string")
    return found


def texts(value: Entry, key: str) -> list[str]:
    """Return a list of strings, or fail."""
    found = value.get(key)
    if not isinstance(found, list) or not all(isinstance(item, str) for item in found):
        fail(TOOL, f"'{key}' is not a list of strings")
    return cast(list[str], found)


def integer(value: Entry, key: str) -> int:
    """Return a non-negative integer field, or fail."""
    found = value.get(key)
    if not isinstance(found, int) or isinstance(found, bool) or found < 0:
        fail(TOOL, f"'{key}' is not a non-negative integer")
    return found


def optional_integer(value: Entry, key: str) -> int | None:
    """Return a positive integer field or None, or fail."""
    if value.get(key) is None:
        return None
    return integer(value, key) or None


def optional_text(value: Entry, key: str) -> str | None:
    """Return a string field or None, or fail."""
    return None if value.get(key) is None else text(value, key)


def flag(value: Entry, key: str) -> bool:
    """Return a boolean field, or fail."""
    found = value.get(key)
    if not isinstance(found, bool):
        fail(TOOL, f"'{key}' is not a boolean")
    return found


def optional_entry(value: Entry, key: str) -> Entry | None:
    """Return an object field or None, or fail."""
    found = value.get(key)
    if found is not None and not isinstance(found, dict):
        fail(TOOL, f"'{key}' is not an object")
    return found
