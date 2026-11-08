"""Owned controllers and native identity checks for nested experiments."""

from __future__ import annotations

import os
import re
import select
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import CGROUP, Group, load, membership
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid


@dataclass
class Worker:
    """Controller process with its own immutable evidence directory."""

    process: subprocess.Popen[bytes]
    output: Path

    def wait(self, deadline: int) -> dict[str, object]:
        timeout = (deadline - time.monotonic_ns()) / 1e9
        if timeout <= 0:
            expired("nested control wait deadline")
        if self.process.wait(timeout=timeout) != 0:
            invalid("nested control worker failed")
        if time.monotonic_ns() >= deadline:
            expired("nested control wait deadline")
        return load(self.output / "result.json")

    def cancel(self) -> None:
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)

    def stop(self, deadline: int) -> None:
        if self.process.poll() is not None:
            self.process.wait()
            return
        self.cancel()
        timeout = max(0.001, min(1.0, (deadline - time.monotonic_ns()) / 1e9))
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=max(0.001, (deadline - time.monotonic_ns()) / 1e9))


def wait_until(predicate: Callable[[], bool], deadline: int) -> None:
    while True:
        if time.monotonic_ns() >= deadline:
            expired("nested proof observation deadline")
        if predicate():
            return
        time.sleep(0.01)


def launch(
    group: Group, repo: Path, output: Path, environment: dict[str, str], argv: list[str], *,
    memory: int, tasks: int, deadline: int, payload_deadline: int,
) -> Worker:
    output.mkdir(parents=True, exist_ok=False)
    lifecycle = int(os.environ["RL00_LIFECYCLE_FD"])
    command = [
        sys.executable, "-m", "tests.acceptance.rl00bc.rl00bc_nested_worker",
        "--group-fd", str(group.fd), "--repo", str(repo), "--output", str(output / "kernel"),
        "--result", str(output / "result.json"), "--memory-mib", str(memory),
        "--tasks", str(tasks), "--deadline", str(deadline),
        "--payload-deadline", str(payload_deadline), "--", *argv,
    ]
    env = {**os.environ, **environment, "PYTHONPATH": str(repo / "tools/quality")}
    for key in ("RL00_LIFECYCLE_FD", "RL00_LIFECYCLE_INODE", "RL00_LIFECYCLE_CLOSING"):
        env[key] = os.environ[key]
    with (output / "worker.log").open("wb") as log:
        process = subprocess.Popen(
            command, cwd=repo, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=log, pass_fds=(group.fd, lifecycle),
        )
    return Worker(process, output)


def native(path: Path, parent: Group, name: str) -> tuple[dict[str, object], int]:
    data = load(path)
    pid, cgroup = data.get("pid"), data.get("cgroup")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        invalid("nested native identity has invalid pid")
    if not isinstance(cgroup, str) or data.get("name") != name:
        invalid("nested native identity is invalid")
    prefix = "/" + str(parent.path.relative_to(CGROUP)) + "/"
    if not cgroup.startswith(prefix) or re.fullmatch(r"[a-f0-9]{32}", cgroup[len(prefix):]) is None:
        invalid("nested native identity is outside its assigned parent")
    if (
        data.get("lifecycle_fd_absent") is not True
        or data.get("lifecycle_environment_absent") is not True
    ):
        invalid("native payload inherited lifecycle authority")
    fd = os.pidfd_open(pid)
    try:
        live(data, fd)
    except BaseException:
        os.close(fd)
        raise
    return data, fd


def live(data: dict[str, object], pidfd: int) -> None:
    pid = data.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int):
        invalid("invalid nested native pid")
    if select.select([pidfd], [], [], 0)[0] or membership(pid) != data.get("cgroup"):
        invalid("nested native parent or child died or changed membership")


def require_success(result: dict[str, object]) -> None:
    if result.get("success") is not True or result.get("cleanup_complete") is not True:
        invalid("nested native execution did not succeed and clean up")
