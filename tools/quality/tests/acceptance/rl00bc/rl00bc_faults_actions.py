"""Controlled faults and post-observation cleanup of descriptor-owned subjects."""

from __future__ import annotations

import fcntl
import os
import signal
import stat
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, membership
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid, unavailable
from tests.acceptance.rl00bc.rl00bc_faults_subject import (
    MIB,
    Subject,
    alive,
    controller_identity,
    entry,
    identity,
    parent_pid,
    work_entry,
)
from tests.acceptance.rl00bc.rl00bc_kernel import lock_lifecycle
from tests.acceptance.rl00bc.rl00bc_lifecycle_support import Worker


def _before_deadline(subject: Subject) -> None:
    if time.monotonic_ns() >= subject.deadline:
        expired("fault probe original deadline")


@contextmanager
def exclusive(subject: Subject) -> Iterator[None]:
    """Use an independent description of the actual guardian lifecycle lock."""
    inherited = int(os.environ["RL00_LIFECYCLE_FD"])
    closing = Path(os.environ["RL00_LIFECYCLE_CLOSING"])
    info = os.fstat(inherited)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_ino != int(os.environ["RL00_LIFECYCLE_INODE"])
            or not closing.is_absolute()):
        invalid("fault probe lifecycle authority is invalid")
    fd = os.open(f"/proc/self/fd/{inherited}", os.O_RDWR | os.O_CLOEXEC)
    try:
        reopened = os.fstat(fd)
        if (reopened.st_dev, reopened.st_ino) != (info.st_dev, info.st_ino):
            invalid("fault probe lifecycle descriptor changed")
        lock_lifecycle(fd, subject.deadline)
        if time.monotonic_ns() >= subject.deadline:
            expired("fault probe lifecycle deadline")
        if closing.exists():
            unavailable("guardian owns cleanup after closing")
        subject.verify_work()
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def kill_requester(subject: Subject) -> int:
    """Signal only the still-owned, pidfd-pinned requester."""
    subject.verify_native()
    subject.verify_requester()
    _before_deadline(subject)
    fired = time.monotonic_ns()
    subject.fault_started_ns = fired
    signal.pidfd_send_signal(subject.worker_fd, signal.SIGKILL)
    return fired


def lower_limit(subject: Subject) -> int:
    """Lower only the owned leaf's task cap without requesting extra work."""
    with exclusive(subject):
        subject.verify_native()
        subject.verify_requester()
        if (subject.leaf.read("memory.max") != str(128 * MIB)
                or subject.leaf.read("memory.swap.max") != "0"
                or subject.leaf.read("pids.max") != "8"
                or int(subject.leaf.read("pids.current")) > 7):
            invalid("fault probe cannot safely lower the leaf task limit")
        subject.verify_leaf()
        _before_deadline(subject)
        fired = time.monotonic_ns()
        subject.fault_started_ns = fired
        subject.leaf.write("pids.max", 7)
        subject.verify_leaf()
        if subject.leaf.read("pids.max") != "7":
            invalid("fault probe lowered limit was not observed")
        return fired


def _target_capacity(subject: Subject) -> tuple[str, str, str]:
    if (subject.leaf.read("memory.max") != str(128 * MIB)
            or subject.leaf.read("pids.max") != "8"
            or subject.leaf.read("memory.swap.max") != "0"):
        invalid("fault probe leaf capacity changed before target reservation")
    with os.scandir(subject.work.fd) as entries:
        found = list(entries)
    if any(entry.is_symlink() for entry in found):
        invalid("fault probe work branch contains a symlink")
    names = [entry.name for entry in found if entry.is_dir(follow_symlinks=False)]
    if names != [subject.leaf.path.name]:
        invalid("fault probe requires only its own live leaf")
    limits = (subject.work.read("memory.max"), subject.work.read("pids.max"),
              subject.work.read("memory.swap.max"))
    if int(limits[0]) < 256 * MIB or int(limits[1]) < 16 or limits[2] != "0":
        invalid("fault probe target exceeds remaining work capacity")
    return limits


def create_target(subject: Subject) -> None:
    """Reserve one finite sibling while holding the actual admission lock."""
    with exclusive(subject):
        subject.verify_native()
        subject.verify_requester()
        limits = _target_capacity(subject)
        subject.verify_leaf()
        if time.monotonic_ns() >= subject.deadline:
            expired("fault probe target setup deadline")
        subject.target = subject.work.bare(uuid.uuid4().hex)
        subject.target_id = identity(subject.target)
        subject.verify_target()
        _before_deadline(subject)
        subject.target.limit(128, 8)
        subject.verify_target()
        _target_limits(subject.target)
        actual = (subject.work.read("memory.max"), subject.work.read("pids.max"),
                  subject.work.read("memory.swap.max"))
        if actual != limits:
            invalid("fault probe work capacity changed during target reservation")


def move_native(subject: Subject) -> int:
    """Move the verified native child only into its own finite sibling."""
    with exclusive(subject):
        subject.verify_native()
        subject.verify_requester()
        subject.verify_target()
        assert subject.target is not None
        _target_limits(subject.target)
        _before_deadline(subject)
        fired = time.monotonic_ns()
        subject.fault_started_ns = fired
        subject.target.write("cgroup.procs", subject.native_pid)
        subject.verify_native(target=True)
        return fired


def _target_limits(group: Group) -> None:
    if (group.read("memory.max") != str(128 * MIB) or group.read("pids.max") != "8"
            or group.read("memory.swap.max") != "0"):
        invalid("fault probe target limits changed")


def _native_owned(subject: Subject) -> bool:
    subject.verify_work()
    if not alive(subject.native_fd):
        return False
    current = membership(subject.native_pid)
    if current == subject.native.get("cgroup"):
        subject.verify_leaf()
    elif subject.target is not None:
        subject.verify_target()
        expected = "/" + str(subject.target.path.relative_to(Path("/sys/fs/cgroup")))
        if current != expected:
            invalid("fault probe native process left its owned branches")
    else:
        invalid("fault probe native process left its owned leaf")
    return True


def _wait_exit(pidfd: int, deadline: int) -> None:
    while alive(pidfd) and time.monotonic_ns() < deadline:
        time.sleep(0.01)


def _stop_worker(subject: Subject) -> None:
    if not alive(subject.worker_fd):
        subject.worker.process.poll()
        return
    subject.verify_worker()
    _before_deadline(subject)
    signal.pidfd_send_signal(subject.worker_fd, signal.SIGINT)
    _wait_exit(subject.worker_fd, min(subject.deadline, time.monotonic_ns() + 1_000_000_000))
    if alive(subject.worker_fd) and time.monotonic_ns() < subject.deadline:
        subject.verify_worker()
        _before_deadline(subject)
        signal.pidfd_send_signal(subject.worker_fd, signal.SIGKILL)
        _wait_exit(subject.worker_fd, subject.deadline)
    if alive(subject.worker_fd):
        unavailable("fault probe requester did not exit by the original deadline")
    subject.worker.process.poll()


def _remove_group(subject: Subject, group: Group, expected: tuple[int, int]) -> bool:
    subject.verify_work()
    try:
        entry(subject.work, group, expected)
    except FileNotFoundError:
        return False
    pids = {int(value) for value in group.read("cgroup.procs").split()}
    if pids and (pids != {subject.native_pid} or not alive(subject.native_fd)):
        invalid("fault cleanup found an unowned or reused process")
    with os.scandir(group.fd) as entries:
        if any(item.is_symlink() or item.is_dir(follow_symlinks=False) for item in entries):
            invalid("fault cleanup found an unexpected descendant group")
    subject.verify_work()
    entry(subject.work, group, expected)
    _before_deadline(subject)
    group.kill()
    subject.verify_work()
    entry(subject.work, group, expected)
    _before_deadline(subject)
    group.remove()
    return True


def _cleanup_groups(subject: Subject, errors: list[str]) -> None:
    try:
        subject.leaf_closed = _remove_group(subject, subject.leaf, subject.leaf_id)
    except (OSError, ValueError, RuntimeError, AssertionError, KeyError, StopIteration) as error:
        errors.append(f"owned leaf: {type(error).__name__}: {error}")
    if subject.target is not None and subject.target_id is not None:
        try:
            subject.target_closed = _remove_group(subject, subject.target, subject.target_id)
        except (OSError, ValueError, RuntimeError, AssertionError, KeyError, StopIteration) as error:
            errors.append(f"owned target: {type(error).__name__}: {error}")


def manual_cleanup(subject: Subject, verdict_observed_ns: int) -> dict[str, object]:
    """Intervene only after the caller has frozen its unassisted verdict."""
    if verdict_observed_ns <= 0 or time.monotonic_ns() < verdict_observed_ns:
        invalid("fault cleanup requires a completed unassisted observation")
    errors: list[str] = []
    result: dict[str, object] = {"started_ns": time.monotonic_ns()}
    try:
        _stop_worker(subject)
    except (OSError, ValueError, RuntimeError, AssertionError, StopIteration) as error:
        errors.append(f"requester: {type(error).__name__}: {error}")
    try:
        with exclusive(subject):
            if _native_owned(subject):
                _before_deadline(subject)
                signal.pidfd_send_signal(subject.native_fd, signal.SIGKILL)
                _wait_exit(subject.native_fd, min(subject.deadline,
                                                  time.monotonic_ns() + 1_000_000_000))
            _cleanup_groups(subject, errors)
    except (OSError, ValueError, RuntimeError, AssertionError, KeyError, StopIteration) as error:
        errors.append(f"owned groups: {type(error).__name__}: {error}")
    result.update(finished_ns=time.monotonic_ns(), errors=errors)
    return result


def _verify_unbound(
    worker: Worker,
    work: Group,
    parent_id: tuple[int, int],
    work_id: tuple[int, int],
    control_id: tuple[int, int],
    control_group: str,
    pidfd: int,
) -> None:
    work_entry(work, parent_id, work_id)
    current_id, current_group = controller_identity(work, parent_id)
    if current_id != control_id or current_group != control_group:
        invalid("unbound controller identity changed")
    if (not alive(pidfd) or parent_pid(worker.process.pid) != os.getpid()
            or membership(worker.process.pid) != control_group):
        invalid("unbound requester identity changed")


def stop_unbound(
    worker: Worker,
    work: Group,
    parent_id: tuple[int, int],
    work_id: tuple[int, int],
    control_id: tuple[int, int],
    control_group: str,
    deadline: int,
) -> dict[str, object]:
    """Best-effort stop of our direct worker when no native leaf could be bound."""
    errors: list[str] = []
    try:
        if worker.process.poll() is None:
            pidfd = os.pidfd_open(worker.process.pid)
            try:
                _verify_unbound(worker, work, parent_id, work_id, control_id, control_group, pidfd)
                if time.monotonic_ns() >= deadline:
                    expired("unbound requester cleanup deadline")
                signal.pidfd_send_signal(pidfd, signal.SIGINT)
                _wait_exit(pidfd, min(deadline, time.monotonic_ns() + 1_000_000_000))
                if alive(pidfd):
                    errors.append("requester remains live; guardian cleanup required")
            finally:
                os.close(pidfd)
        worker.process.poll()
    except (OSError, ValueError, RuntimeError, AssertionError, StopIteration) as error:
        errors.append(f"unbound requester: {type(error).__name__}: {error}")
    return {"finished_ns": time.monotonic_ns(), "errors": errors,
            "leaf_cleanup": "unverified; guardian cleanup required"}
