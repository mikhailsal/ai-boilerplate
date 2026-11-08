"""Process and evidence helpers for bounded RL00bc lifecycle probes."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import CGROUP, Group, load
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid


@dataclass
class Worker:
    """One owned proof controller and its separate evidence paths."""

    process: subprocess.Popen[bytes]
    root: Path
    deadline: int

    def path(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def result(self) -> dict[str, object]:
        return load(self.path("result"))

    def release(self) -> None:
        self.path("release").touch()

    def wait(self, until: int) -> None:
        timeout = max(0.001, (until - time.monotonic_ns()) / 1e9)
        if self.process.wait(timeout=timeout) != 0:
            invalid("lifecycle worker exited without evidence")

    def cancel(self) -> None:
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)

    def stop(self, deadline: int) -> None:
        if self.process.poll() is not None:
            self.process.wait()
            return
        self.cancel()
        try:
            self.process.wait(timeout=max(0.001, min(1.0, (deadline - time.monotonic_ns()) / 1e9)))
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=max(0.001, min(1.0, (deadline - time.monotonic_ns()) / 1e9)))


def until(predicate: Callable[[], bool], deadline: int) -> None:
    while not predicate():
        if time.monotonic_ns() >= deadline:
            expired("lifecycle proof observation deadline")
        time.sleep(0.01)


def children(work: Group) -> list[str]:
    with os.scandir(work.fd) as entries:
        return sorted(entry.name for entry in entries if entry.is_dir(follow_symlinks=False))


def start(
    work: Group,
    repo: Path,
    output: Path,
    environment: dict[str, str],
    *,
    memory_mib: int,
    tasks: int,
    deadline: int,
    payload_deadline: int,
    hold_lock: bool = False,
) -> Worker:
    output.mkdir(parents=True, exist_ok=False)
    lifecycle_fd = int(os.environ["RL00_LIFECYCLE_FD"])
    command = [
        sys.executable,
        "-m",
        "tests.acceptance.rl00bc.rl00bc_lifecycle_child",
        "worker",
        "--work-fd",
        str(work.fd),
        "--repo",
        str(repo),
        "--output",
        str(output / "kernel"),
        "--marker",
        str(output / "marker.json"),
        "--release",
        str(output / "release.json"),
        "--attempt",
        str(output / "attempt.json"),
        "--result",
        str(output / "result.json"),
        "--memory-mib",
        str(memory_mib),
        "--tasks",
        str(tasks),
        "--deadline",
        str(deadline),
        "--payload-deadline",
        str(payload_deadline),
    ]
    if hold_lock:
        command.extend(
            ["--held", str(output / "held.json"), "--proceed", str(output / "proceed.json")]
        )
    env = {**os.environ, **environment, "PYTHONPATH": str(repo / "tools/quality")}
    for key in ("RL00_LIFECYCLE_FD", "RL00_LIFECYCLE_INODE", "RL00_LIFECYCLE_CLOSING"):
        env[key] = os.environ[key]
    with (output / "worker.log").open("wb") as log:
        process = subprocess.Popen(
            command,
            cwd=repo,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=log,
            pass_fds=(work.fd, lifecycle_fd),
        )
    return Worker(process, output, deadline)


def marker(worker: Worker, work: Group) -> dict[str, object]:
    data = load(worker.path("marker"))
    expected = "/" + str(work.path.relative_to(CGROUP)) + "/"
    group = data.get("cgroup")
    if not isinstance(group, str) or not group.startswith(expected):
        invalid("native marker is outside the owned work branch")
    pid = data.get("pid")
    if re.fullmatch(r"[a-f0-9]{32}", group[len(expected) :]) is None:
        invalid("native marker does not identify a direct leaf")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        invalid("native marker does not identify a direct leaf")
    return data


def require_marker_result(native: dict[str, object], result: dict[str, object]) -> None:
    """Tie the native marker to the leaf recorded by the kernel observation."""
    raw = result.get("before")
    if not isinstance(raw, dict):
        invalid("kernel leaf identity is unavailable")
    path = cast(dict[str, object], raw).get("path")
    if not isinstance(path, str):
        invalid("kernel leaf path is unavailable")
    expected = "/" + str(Path(path).relative_to(CGROUP))
    if native.get("cgroup") != expected:
        invalid("native marker differs from the observed kernel leaf")


def require_clean(work: Group, initial: list[str]) -> None:
    if children(work) != initial:
        invalid("lifecycle proof left or changed work children")
