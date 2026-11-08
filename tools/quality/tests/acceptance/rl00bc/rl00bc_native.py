"""Run a finite native sequence in one protected subject and absolute deadline.

This direct-file helper imports only the standard library. Preparation commands
and the final runner retain placement; the outer guardian owns enforcement.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, cast


@dataclass(frozen=True)
class Plan:
    """Validated paths, commands and original absolute native deadline."""

    cwd: Path
    stages: list[list[str]]
    output: Path
    deadline_ns: int


def _invalid(message: str) -> NoReturn:
    raise ValueError(message)


def _expired(message: str) -> NoReturn:
    raise TimeoutError(message)


def _path(value: object) -> Path:
    if not isinstance(value, str) or "\0" in value:
        _invalid("native command path must be a string")
    result = Path(value)
    if not result.is_absolute():
        _invalid("native command path must be absolute")
    return result


def _argv(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        _invalid("native command must be a nonempty argv")
    items = cast(list[object], value)
    if not all(isinstance(item, str) and "\0" not in item for item in items):
        _invalid("native argv entries must be strings without NUL")
    result = cast(list[str], items)
    _path(result[0])
    return result


def _stages(value: object) -> list[list[str]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 4:
        _invalid("native command sequence must have one to four stages")
    return [_argv(item) for item in cast(list[object], value)]


def commands(path: Path) -> Plan:
    """Read a size-bounded plan and reject invalid paths before any command."""
    if path.stat().st_size > 65536:
        _invalid("native command plan is oversized")
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        _invalid("native command plan must be an object")
    data = cast(dict[str, object], value)
    deadline = data.get("deadline_ns")
    if type(deadline) is not int or deadline <= time.monotonic_ns():
        _invalid("native command plan has no remaining absolute deadline")
    cwd = _path(data.get("cwd"))
    if not cwd.is_dir():
        _invalid("native command working directory is missing")
    return Plan(cwd, _stages(data.get("commands")), _path(data.get("events")), deadline)


def _started(plan: Plan, index: int) -> dict[str, object]:
    record: dict[str, object] = {
        "index": index,
        "started_ns": time.monotonic_ns(),
        "pid": os.getpid(),
        "uid": os.getuid(),
        "cgroup": Path("/proc/self/cgroup").read_text(),
    }
    _save(plan, index, record)
    return record


def _save(plan: Plan, index: int, record: dict[str, object]) -> None:
    (plan.output / f"native-stage-{index}.json").write_text(json.dumps(record) + "\n")


def _stage(plan: Plan, index: int, argv: list[str]) -> int:
    remaining = (plan.deadline_ns - time.monotonic_ns()) / 1_000_000_000
    if remaining <= 0:
        _expired("native command deadline expired")
    record = _started(plan, index)
    if index == len(plan.stages) - 1:
        os.execve(argv[0], argv, os.environ)
    completed = subprocess.run(argv, check=False, timeout=remaining)
    record.update(finished_ns=time.monotonic_ns(), native_status=completed.returncode)
    _save(plan, index, record)
    return completed.returncode if completed.returncode >= 0 else 128 - completed.returncode


def run(path: Path) -> int:
    """Keep prefix commands and final exec under the original native envelope."""
    plan = commands(path)
    plan.output.mkdir(parents=True, exist_ok=True)
    os.chdir(plan.cwd)
    for index, argv in enumerate(plan.stages):
        status = _stage(plan, index, argv)
        if status != 0:
            return status
    message = "native final exec returned"
    raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1])))
