"""Dedicated controller for one opt-in, real guardian race unit."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, save
from tests.acceptance.rl00bc import rl00bc_control, rl00bc_kernel
from tests.acceptance.rl00bc.rl00bc_guardian_race_support import wait_file
from tests.acceptance.rl00bc.rl00bc_lifecycle_support import children


def _gate(output: Path) -> None:
    original = rl00bc_kernel.handshake

    def handshake(process: subprocess.Popen[bytes], fd: int, deadline: int) -> None:
        try:
            save(
                output / "race-handshake-held.json",
                {
                    "held_ns": time.monotonic_ns(),
                    "pid": process.pid,
                    "lifecycle_inode": int(os.environ["RL00_LIFECYCLE_INODE"]),
                },
            )
            wait_file(output / "race-release.json", deadline)
        except BaseException:
            os.close(fd)
            raise
        original(process, fd, deadline)

    rl00bc_kernel.handshake = handshake


def _execute(work: Group, args: argparse.Namespace) -> dict[str, object]:
    repo = Path(__file__).resolve().parents[5]
    argv = [
        sys.executable,
        "-m",
        "tests.acceptance.rl00bc.rl00bc_lifecycle_child",
        "payload",
        "--marker",
        str(args.output / "race-marker.json"),
        "--release",
        str(args.output / "race-payload-release.json"),
        "--deadline",
        str(args.deadline_ns),
    ]
    return rl00bc_kernel.execute(
        work,
        argv,
        repo,
        {**os.environ, "PYTHONPATH": str(repo / "tools/quality")},
        args.output / "race-kernel",
        memory_mib=128,
        tasks=8,
        native_seconds=60,
        ancestor_deadline_ns=args.deadline_ns,
    )


def _closing_first(work: Group, args: argparse.Namespace) -> None:
    before = children(work)
    save(
        args.output / "race-controller-ready.json",
        {"ready_ns": time.monotonic_ns(), "work_inode": work.inode},
    )
    wait_file(args.output / "race-release.json", args.deadline_ns - 3_000_000_000)
    result = _execute(work, args)
    save(
        args.output / "race-controller-done.json",
        {
            "observed_ns": time.monotonic_ns(),
            "work_inode": work.inode,
            "children_before": before,
            "children_after": children(work),
            "native_marker_exists": (args.output / "race-marker.json").exists(),
            "result": result,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--race", choices=("launch-first", "closing-first"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deadline-ns", type=int, required=True)
    parser.add_argument("--lifecycle-fd", type=int, required=True)
    parser.add_argument("--work-fd", type=int)
    parser.add_argument("--parent-fd", type=int)
    parser.add_argument("--work-name")
    args = parser.parse_args()
    work = rl00bc_control.work_group(args)
    try:
        if args.race == "launch-first":
            _gate(args.output)
            result = _execute(work, args)
            save(args.output / "race-controller-returned.json", result)
            if result.get("success") is not True:
                return 2
        else:
            _closing_first(work, args)
            return 2
    finally:
        os.close(work.fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
