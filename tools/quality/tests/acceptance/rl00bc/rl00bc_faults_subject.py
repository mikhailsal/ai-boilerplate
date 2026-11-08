"""Pin only the worker and cgroup leaf created for one bounded fault probe."""

from __future__ import annotations

import os
import select
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group, membership
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid
from tests.acceptance.rl00bc.rl00bc_lifecycle_support import Worker, marker, until

MIB = 1024 * 1024


def alive(pidfd: int) -> bool:
    """Read the kernel pidfd state without inferring why the process exited."""
    return not select.select([pidfd], [], [], 0)[0]


def identity(group: Group) -> tuple[int, int]:
    """Verify an opened cgroup still identifies its own pathname."""
    info = os.fstat(group.fd)
    path = group.path.stat()
    if info.st_ino != group.inode or (info.st_dev, info.st_ino) != (path.st_dev, path.st_ino):
        invalid("fault probe cgroup identity changed")
    return info.st_dev, info.st_ino


def entry(parent: Group, child: Group, expected: tuple[int, int]) -> None:
    """Verify the direct parent entry against the pinned child descriptor."""
    if child.path.parent != parent.path or identity(child) != expected:
        invalid("fault probe cgroup parent or identity changed")
    fd = os.open(
        child.path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=parent.fd,
    )
    try:
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != expected:
            invalid("fault probe parent entry changed")
    finally:
        os.close(fd)


def work_entry(work: Group, parent_id: tuple[int, int], work_id: tuple[int, int]) -> None:
    """Verify the work directory through its independently opened parent."""
    parent_fd = os.open(work.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parent = os.fstat(parent_fd)
        if (parent.st_dev, parent.st_ino) != parent_id or identity(work) != work_id:
            invalid("fault probe work parent identity changed")
        child_fd = os.open(work.path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                           dir_fd=parent_fd)
        try:
            child = os.fstat(child_fd)
            if (child.st_dev, child.st_ino) != work_id:
                invalid("fault probe work parent entry changed")
        finally:
            os.close(child_fd)
    finally:
        os.close(parent_fd)


def parent_pid(pid: int) -> int:
    """Read the native or requester process's live parent identity."""
    lines = Path(f"/proc/{pid}/status").read_text().splitlines()
    parent = next(line.split()[1] for line in lines if line.startswith("PPid:"))
    return int(parent)


def controller_identity(work: Group, parent_id: tuple[int, int]) -> tuple[tuple[int, int], str]:
    """Anchor the current control leaf to the same verified unit parent."""
    control = Group.current()
    try:
        if control.path.parent != work.path.parent:
            invalid("fault probe control and work parents differ")
        control_id = identity(control)
        work_entry(control, parent_id, control_id)
        return control_id, membership()
    finally:
        os.close(control.fd)


@dataclass
class Subject:
    """Descriptor and pidfd ownership for the actual launched payload."""

    work: Group
    worker: Worker
    worker_fd: int
    native_pid: int
    native_fd: int
    native: dict[str, object]
    worker_cgroup: str
    controller_id: tuple[int, int]
    leaf: Group
    work_parent_id: tuple[int, int]
    work_id: tuple[int, int]
    work_limits: tuple[str, str, str]
    leaf_id: tuple[int, int]
    deadline: int
    target: Group | None = None
    target_id: tuple[int, int] | None = None
    leaf_closed: bool = False
    target_closed: bool = False
    fault_started_ns: int | None = None

    def verify_work(self) -> None:
        work_entry(self.work, self.work_parent_id, self.work_id)
        limits = (self.work.read("memory.max"), self.work.read("pids.max"),
                  self.work.read("memory.swap.max"))
        if limits != self.work_limits:
            invalid("fault probe work limits changed")

    def verify_leaf(self) -> None:
        self.verify_work()
        entry(self.work, self.leaf, self.leaf_id)

    def verify_target(self) -> None:
        self.verify_work()
        if self.target is None or self.target_id is None:
            invalid("fault probe target is unavailable")
        entry(self.work, self.target, self.target_id)

    def verify_native(self, *, target: bool = False) -> None:
        self.verify_leaf()
        if not alive(self.native_fd):
            invalid("fault probe native process already exited")
        expected = self.native.get("cgroup")
        if target:
            self.verify_target()
            assert self.target is not None
            expected = "/" + str(self.target.path.relative_to(Path("/sys/fs/cgroup")))
        if membership(self.native_pid) != expected:
            invalid("fault probe native membership changed unexpectedly")

    def verify_worker(self) -> None:
        self.verify_work()
        control_id, group = controller_identity(self.work, self.work_parent_id)
        if control_id != self.controller_id or group != self.worker_cgroup:
            invalid("fault probe controller identity changed")
        if not alive(self.worker_fd) or self.worker.process.poll() is not None:
            invalid("fault probe requester already exited")
        if (parent_pid(self.worker.process.pid) != os.getpid()
                or membership(self.worker.process.pid) != self.worker_cgroup):
            invalid("fault probe requester ownership changed")

    def verify_requester(self) -> None:
        self.verify_worker()
        if parent_pid(self.native_pid) != self.worker.process.pid:
            invalid("fault probe native process is not the requester's child")

    def leaf_present(self) -> bool:
        """Observe absence only through the verified, pinned work directory."""
        self.verify_work()
        pinned = os.fstat(self.leaf.fd)
        if (pinned.st_dev, pinned.st_ino) != self.leaf_id:
            invalid("fault probe leaf descriptor changed")
        try:
            fd = os.open(self.leaf.path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=self.work.fd)
        except FileNotFoundError:
            return False
        try:
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) != self.leaf_id:
                invalid("fault probe leaf entry changed")
        finally:
            os.close(fd)
        return True

    def close(self) -> list[str]:
        errors: list[str] = []
        descriptors = [self.native_fd, self.worker_fd]
        if not self.leaf_closed:
            descriptors.append(self.leaf.fd)
        if self.target is not None and not self.target_closed:
            descriptors.append(self.target.fd)
        for descriptor in descriptors:
            try:
                os.close(descriptor)
            except OSError as error:
                errors.append(f"descriptor: {type(error).__name__}: {error}")
        return errors


def _marker_pid(native: dict[str, object]) -> int:
    started = native.get("started_ns")
    if (isinstance(started, bool) or not isinstance(started, int)
            or not 0 < started <= time.monotonic_ns()):
        invalid("fault probe native start timestamp is invalid")
    return cast(int, native["pid"])


def _bind_leaf(
    work: Group, worker: Worker, worker_fd: int, native: dict[str, object],
    native_fd: int, deadline: int,
) -> Subject:
    work_id = identity(work)
    parent = work.path.parent.stat()
    work_parent_id = (parent.st_dev, parent.st_ino)
    work_entry(work, work_parent_id, work_id)
    work_limits = (work.read("memory.max"), work.read("pids.max"), work.read("memory.swap.max"))
    if int(work_limits[0]) < 128 * MIB or int(work_limits[1]) < 8 or work_limits[2] != "0":
        invalid("fault probe work limits are insufficient")
    control_id, control_group = controller_identity(work, work_parent_id)
    worker_group = membership(worker.process.pid)
    if worker_group != control_group:
        invalid("fault probe requester is outside the bounded controller")
    leaf = work.adopt(Path(str(native["cgroup"])).name)
    try:
        subject = Subject(
            work, worker, worker_fd, cast(int, native["pid"]), native_fd, native,
            worker_group, control_id, leaf, work_parent_id, work_id, work_limits,
            identity(leaf), deadline,
        )
        subject.verify_leaf()
        subject.verify_native()
        subject.verify_requester()
        if (leaf.read("memory.max") != str(128 * MIB) or leaf.read("pids.max") != "8"
                or leaf.read("memory.swap.max") != "0"):
            invalid("fault probe leaf has unexpected limits")
        if time.monotonic_ns() >= deadline - 8_000_000_000:
            expired("insufficient remaining original fault deadline")
    except BaseException:
        os.close(leaf.fd)
        raise
    return subject


def open_subject(work: Group, worker: Worker, deadline: int) -> Subject:
    """Bind the real kernel worker's live marker to a direct child leaf."""
    worker_fd = os.pidfd_open(worker.process.pid)
    try:
        until(worker.path("marker").is_file, min(deadline - 8_000_000_000,
                                                  time.monotonic_ns() + 8_000_000_000))
        native = marker(worker, work)
        native_fd = os.pidfd_open(_marker_pid(native))
        try:
            subject = _bind_leaf(work, worker, worker_fd, native, native_fd, deadline)
        except BaseException:
            os.close(native_fd)
            raise
    except BaseException:
        os.close(worker_fd)
        raise
    return subject
