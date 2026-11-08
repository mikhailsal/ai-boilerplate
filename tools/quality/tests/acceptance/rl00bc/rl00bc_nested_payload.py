"""Native parent and child payloads for the bounded nested-capacity experiment."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import NoReturn, cast


def _fail(message: str) -> NoReturn:
    raise RuntimeError(message)


def _save(path: Path, value: object) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n")
    temporary.replace(path)


def _wait(path: Path, deadline: int) -> None:
    while True:
        if time.monotonic_ns() >= deadline:
            _fail("native mailbox deadline expired")
        if path.is_file():
            return
        time.sleep(0.01)


def _identity(name: str, lock_dev: int, lock_ino: int) -> dict[str, object]:
    membership = Path("/proc/self/cgroup").read_text().splitlines()
    cgroup = next(line.removeprefix("0::") for line in membership if line.startswith("0::"))
    leaked = False
    for descriptor in Path("/proc/self/fd").iterdir():
        try:
            info = descriptor.stat()
        except FileNotFoundError:
            continue
        leaked = leaked or (info.st_dev, info.st_ino) == (lock_dev, lock_ino)
    authority_names = ("RL00_LIFECYCLE_FD", "RL00_LIFECYCLE_INODE", "RL00_LIFECYCLE_CLOSING")
    return {
        "name": name, "pid": os.getpid(), "cgroup": cgroup,
        "monotonic_ns": time.monotonic_ns(), "lifecycle_fd_absent": not leaked,
        "lifecycle_environment_absent": not any(key in os.environ for key in authority_names),
    }


def _requests(memory: int, tasks: int) -> tuple[tuple[str, int, int], ...]:
    return (
        ("concurrent", 64, 8),
        ("over-memory", memory + 1, 8),
        ("over-tasks", 64, tasks + 1),
        ("cancel", 64, 8),
        ("recovery", 64, 8),
        ("deadline", 64, 8),
    )


def _parent(args: argparse.Namespace) -> int:
    args.mailbox.mkdir(parents=True, exist_ok=True)
    _save(args.mailbox / "identity.json", _identity(args.name, args.lock_dev, args.lock_ino))
    for index, (kind, memory, tasks) in enumerate(_requests(args.pool_memory, args.pool_tasks)):
        requested_deadline = args.deadline
        if kind == "deadline":
            requested_deadline += 60_000_000_000
        _save(args.mailbox / f"request-{index}.json", {
            "parent": args.name, "pid": os.getpid(), "kind": kind,
            "memory_mib": memory, "tasks": tasks, "requested_ns": time.monotonic_ns(),
            "requested_deadline_ns": requested_deadline,
        })
        response = args.mailbox / f"response-{index}.json"
        _wait(response, args.deadline)
        value: object = json.loads(response.read_text())
        if (
            not isinstance(value, dict)
            or cast(dict[str, object], value).get("accepted") is not True
        ):
            _fail("nested controller rejected or failed the expected proof request")
    _save(args.mailbox / "completed.json", {"completed_ns": time.monotonic_ns()})
    return 0


def _child(args: argparse.Namespace) -> int:
    _save(args.marker, _identity(args.name, args.lock_dev, args.lock_ino))
    _wait(args.release, args.deadline)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("parent", "child"))
    parser.add_argument("--name", required=True)
    parser.add_argument("--deadline", type=int, required=True)
    parser.add_argument("--lock-dev", type=int, required=True)
    parser.add_argument("--lock-ino", type=int, required=True)
    parser.add_argument("--mailbox", type=Path)
    parser.add_argument("--pool-memory", type=int)
    parser.add_argument("--pool-tasks", type=int)
    parser.add_argument("--marker", type=Path)
    parser.add_argument("--release", type=Path)
    args = parser.parse_args()
    if args.mode == "parent":
        if args.mailbox is None or args.pool_memory is None or args.pool_tasks is None:
            parser.error("parent mailbox and pool limits are required")
        return _parent(args)
    if args.marker is None or args.release is None:
        parser.error("child marker and release are required")
    return _child(args)


if __name__ == "__main__":
    raise SystemExit(main())
