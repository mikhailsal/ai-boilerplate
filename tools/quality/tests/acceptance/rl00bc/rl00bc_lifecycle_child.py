"""Bounded worker and native marker for the RL00bc lifecycle experiment."""

from __future__ import annotations

import argparse
import fcntl
import os
import sys
import time
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, membership, save
from tests.acceptance.rl00bc import rl00bc_kernel
from tests.acceptance.rl00bc.rl00bc_errors import expired


def _payload(marker: Path, release: Path, deadline: int) -> int:
    save(marker, {"pid": os.getpid(), "cgroup": membership(), "started_ns": time.monotonic_ns()})
    while not release.exists():
        if time.monotonic_ns() >= deadline:
            expired("proof payload release deadline")
        time.sleep(0.01)
    return 0


def _observe_first_lock(attempt: Path, held: Path | None, proceed: Path | None) -> None:
    original_lock = rl00bc_kernel.lock_lifecycle
    first_attempt = True

    def observed_lock(fd: int, deadline: int) -> None:
        nonlocal first_attempt
        initial = first_attempt
        if initial:
            first_attempt = False
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                state = "blocked"
            else:
                state = "acquired"
                fcntl.flock(fd, fcntl.LOCK_UN)
            save(attempt, {"attempt_ns": time.monotonic_ns(), "state": state})
        original_lock(fd, deadline)
        if initial and held is not None and proceed is not None:
            save(held, {"held_ns": time.monotonic_ns()})
            while not proceed.exists():
                if time.monotonic_ns() >= deadline:
                    expired("proof admission lock gate deadline")
                time.sleep(0.005)

    rl00bc_kernel.lock_lifecycle = observed_lock


def _worker(args: argparse.Namespace) -> int:
    work = Group(args.work_fd, Path(f"/proc/self/fd/{args.work_fd}").readlink())
    _observe_first_lock(args.attempt, args.held, args.proceed)
    try:
        try:
            record = rl00bc_kernel.execute(
                work,
                [
                    sys.executable,
                    "-m",
                    "tests.acceptance.rl00bc.rl00bc_lifecycle_child",
                    "payload",
                    "--marker",
                    str(args.marker),
                    "--release",
                    str(args.release),
                    "--deadline",
                    str(args.payload_deadline),
                ],
                args.repo,
                {**os.environ, "PYTHONPATH": str(args.repo / "tools/quality")},
                args.output,
                memory_mib=args.memory_mib,
                tasks=args.tasks,
                native_seconds=60,
                ancestor_deadline_ns=args.deadline,
                payload_deadline_ns=args.payload_deadline,
            )
        except (ValueError, TimeoutError) as error:
            record = {"raised": f"{type(error).__name__}: {error}", "success": False}
        save(args.result, record)
    finally:
        os.close(work.fd)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("worker", "payload"))
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--deadline", type=int, required=True)
    parser.add_argument("--work-fd", type=int)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--memory-mib", type=int)
    parser.add_argument("--tasks", type=int)
    parser.add_argument("--payload-deadline", type=int)
    parser.add_argument("--held", type=Path)
    parser.add_argument("--proceed", type=Path)
    args = parser.parse_args()
    if args.mode == "payload":
        return _payload(args.marker, args.release, args.deadline)
    required = (
        args.work_fd,
        args.repo,
        args.output,
        args.attempt,
        args.result,
        args.memory_mib,
        args.tasks,
        args.payload_deadline,
    )
    if any(value is None for value in required):
        parser.error("worker arguments are required")
    return _worker(args)


if __name__ == "__main__":
    raise SystemExit(main())
