"""Descriptor-owned primitives for the opt-in RL00a kernel experiment."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

MIB = 1024 * 1024
CGROUP = Path("/sys/fs/cgroup")
HERE = Path(__file__).resolve().parent
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
NAME = re.compile(r"[a-f0-9]{32}")
SHIM = 'printf "%s\\n" "$$" > /proc/self/fd/"$1" || exit 97; shift; exec "$@"'


def save(path: Path, record: object) -> None:
    path.with_suffix(".tmp").write_text(json.dumps(record, indent=2) + "\n")
    path.with_suffix(".tmp").replace(path)


def load(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text())
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def membership(pid: int | str = "self") -> str:
    lines = Path(f"/proc/{pid}/cgroup").read_text().splitlines()
    return next(line.removeprefix("0::") for line in lines if line.startswith("0::"))


def counters(text: str) -> dict[str, int]:
    return {name: int(value) for name, value in (line.split() for line in text.splitlines())}


class Group:
    def __init__(self, fd: int, path: Path, parent: Group | None = None) -> None:
        self.fd = fd
        self.path = path
        self.parent = parent
        self.inode = os.fstat(fd).st_ino

    @classmethod
    def current(cls) -> Group:
        relative = membership().removeprefix("/")
        fd = os.open(CGROUP, DIRECTORY)
        try:
            for part in Path(relative).parts:
                child = os.open(part, DIRECTORY, dir_fd=fd)
                os.close(fd)
                fd = child
        except BaseException:
            os.close(fd)
            raise
        return cls(fd, CGROUP / relative)

    def read(self, name: str) -> str:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.fd)
        try:
            return os.read(fd, 65536).decode().strip()
        finally:
            os.close(fd)

    def write(self, name: str, value: str | int) -> None:
        fd = os.open(name, os.O_WRONLY | os.O_NOFOLLOW, dir_fd=self.fd)
        try:
            os.write(fd, str(value).encode())
        finally:
            os.close(fd)

    def enable(self) -> None:
        assert not self.read("cgroup.procs"), "internal branch must be empty"
        assert {"memory", "pids"} <= set(self.read("cgroup.controllers").split())
        self.write("cgroup.subtree_control", "+memory +pids")

    def create(self, name: str, mib: int, tasks: int) -> Group:
        assert 0 < mib * MIB <= int(self.read("memory.max")), "above ancestor memory"
        assert 0 < tasks <= int(self.read("pids.max")), "above ancestor tasks"
        child = self.bare(name)
        child.limit(mib, tasks)
        return child

    def limit(self, mib: int, tasks: int) -> None:
        self.write("memory.max", mib * MIB)
        self.write("memory.swap.max", 0)
        self.write("pids.max", tasks)

    def bare(self, name: str) -> Group:
        assert NAME.fullmatch(name), "opaque generated child name required"
        os.mkdir(name, dir_fd=self.fd)
        return self.adopt(name)

    def adopt(self, name: str) -> Group:
        assert NAME.fullmatch(name), "unsafe or stale child name"
        return Group(os.open(name, DIRECTORY, dir_fd=self.fd), self.path / name, self)

    def snapshot(self) -> dict[str, object]:
        fields = ("memory.max", "memory.current", "memory.swap.max", "pids.max", "pids.current")
        result: dict[str, object] = {field: self.read(field) for field in fields}
        for field in ("memory.events", "memory.events.local", "pids.events", "cgroup.events"):
            result[field] = counters(self.read(field))
        try:
            result["memory.peak"] = self.read("memory.peak")
        except FileNotFoundError:
            result["memory.peak"] = None
        return {"path": str(self.path), "inode": self.inode, **result}

    def empty(self) -> bool:
        return counters(self.read("cgroup.events"))["populated"] == 0

    def kill(self) -> float:
        started = time.monotonic()
        self.write("cgroup.kill", 1)
        while not self.empty() and time.monotonic() - started < 1:
            time.sleep(0.005)
        assert self.empty(), "owned descendants remain after cgroup.kill"
        return time.monotonic() - started

    def remove(self) -> None:
        with os.scandir(self.fd) as entries:
            names = [entry.name for entry in entries if entry.is_dir(follow_symlinks=False)]
        for name in names:
            self.adopt(name).remove()
        assert self.empty(), "refuse removal of populated group"
        assert self.parent is not None, "delegated root removal belongs to provider"
        os.rmdir(self.path.name, dir_fd=self.parent.fd)
        os.close(self.fd)


def launch(
    group: Group, argv: list[str], inherited: tuple[int, ...] = ()
) -> subprocess.Popen[bytes]:
    fd = os.open("cgroup.procs", os.O_WRONLY | os.O_NOFOLLOW, dir_fd=group.fd)
    try:
        return subprocess.Popen(
            ["/bin/sh", "-c", SHIM, "rl00a-placement", str(fd), *argv],
            pass_fds=(fd, *inherited),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    finally:
        os.close(fd)


def payload(group: Group, action: str, ready: Path, *args: str) -> subprocess.Popen[bytes]:
    return launch(
        group, [sys.executable, str(HERE / "rl00a_payload.py"), action, str(ready), *args]
    )


def wait_ready(process: subprocess.Popen[bytes], ready: Path, group: Group) -> dict[str, object]:
    until = time.monotonic() + 1.5
    record: dict[str, object] = {}
    while time.monotonic() < until:
        record = load(ready) if ready.exists() else {}
        if "cgroup" in record or process.poll() is not None:
            break
        time.sleep(0.005)
    assert "cgroup" in record, f"payload did not reach first statement: {process.poll()}"
    assert record["cgroup"] == f"0::/{group.path.relative_to(CGROUP).as_posix()}\n"
    assert record["uid"] == os.getuid() != 0
    assert record["time_namespace"] == str(Path("/proc/self/ns/time").readlink())
    return record


def sampled_wait(
    process: subprocess.Popen[bytes], group: Group, payload_stop_ns: int
) -> tuple[int, int]:
    high = 0
    while process.poll() is None and time.monotonic_ns() < payload_stop_ns:
        high = max(high, int(group.read("memory.current")))
        time.sleep(0.002)
    assert process.poll() is not None, "bounded workload did not finish before its deadline"
    return process.wait(timeout=0.2), high
