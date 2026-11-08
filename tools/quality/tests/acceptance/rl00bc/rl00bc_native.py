"""Run a frozen native command sequence inside one already protected subject.

Preparation commands and the final runner retain the same cgroup and deadline.
The outer guardian owns time, memory, task and cleanup enforcement. This helper
never provisions a group, resets a deadline or grants a compliance verdict.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def commands(path: Path) -> tuple[Path, list[list[str]], Path, int]:
    if path.stat().st_size > 65536:
        raise ValueError("native command plan is oversized")
    data = json.loads(path.read_text(encoding="utf-8"))
    cwd, stages = Path(data["cwd"]), data["commands"]
    output = Path(data["events"])
    deadline_ns = data["deadline_ns"]
    if type(deadline_ns) is not int or deadline_ns <= time.monotonic_ns():
        raise ValueError("native command plan has no remaining absolute deadline")
    if not cwd.is_absolute() or not cwd.is_dir() or not output.is_absolute():
        raise ValueError("native command paths must be absolute")
    if not isinstance(stages, list) or not 1 <= len(stages) <= 4:
        raise ValueError("native command sequence must be finite")
    for argv in stages:
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(arg, str) and "\0" not in arg for arg in argv)
            or not Path(argv[0]).is_absolute()
        ):
            raise ValueError("native argv must have an absolute executable")
    return cwd, stages, output, deadline_ns


def run(path: Path) -> int:
    cwd, stages, output, deadline_ns = commands(path)
    output.mkdir(parents=True, exist_ok=True)
    os.chdir(cwd)
    for index, argv in enumerate(stages):
        remaining_seconds = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
        if remaining_seconds <= 0:
            raise TimeoutError("native command deadline expired")
        record = {
            "index": index,
            "started_ns": time.monotonic_ns(),
            "pid": os.getpid(),
            "uid": os.getuid(),
            "cgroup": Path("/proc/self/cgroup").read_text(),
        }
        (output / f"native-stage-{index}.json").write_text(json.dumps(record) + "\n")
        if index == len(stages) - 1:
            os.execvpe(argv[0], argv, os.environ)
        completed = subprocess.run(argv, check=False, timeout=remaining_seconds)
        record.update(finished_ns=time.monotonic_ns(), native_status=completed.returncode)
        (output / f"native-stage-{index}.json").write_text(json.dumps(record) + "\n")
        if completed.returncode != 0:
            return completed.returncode if completed.returncode > 0 else 128 - completed.returncode
    raise AssertionError("native final exec returned")


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1])))
