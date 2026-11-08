"""Live identity and limit checks for an already admitted native subject.

The caller owns the returned pidfd and must close the capture. An exited pidfd
is reported separately: it must be classified from native wait status and event
counters, not converted into either compliance or an integrity violation.
Checks sample the process leader; they do not continuously prove that every
descendant stays inside its declared scope.
"""

from __future__ import annotations

import os
import select
from dataclasses import dataclass

from tests.acceptance.rl00a.rl00a_cgroup import CGROUP, Group, membership
from tests.acceptance.rl00bc.rl00bc_errors import invalid, unavailable

LimitTriple = tuple[str, str, str]


def _limits(group: Group) -> LimitTriple:
    return (group.read("memory.max"), group.read("pids.max"), group.read("memory.swap.max"))


def _identity(group: Group) -> tuple[int, int]:
    descriptor = os.fstat(group.fd)
    path = group.path.stat()
    if (descriptor.st_dev, descriptor.st_ino) != (path.st_dev, path.st_ino):
        invalid("cgroup path and descriptor identity differ")
    if descriptor.st_ino != group.inode:
        invalid("cgroup descriptor identity changed")
    return descriptor.st_dev, descriptor.st_ino


def _expected_membership(leaf: Group) -> str:
    return "/" + str(leaf.path.relative_to(CGROUP))


def _alive(pidfd: int) -> bool:
    return not select.select([pidfd], [], [], 0)[0]


@dataclass(frozen=True)
class Capture:
    """Pinned identities and expected limits; close after the final observation.

    The subject must remain an unreaped owned child until this capture is made.
    """

    pid: int
    pidfd: int
    work_identity: tuple[int, int]
    leaf_identity: tuple[int, int]
    work_limits: LimitTriple
    leaf_limits: LimitTriple
    expected_membership: str

    def close(self) -> None:
        os.close(self.pidfd)


def _validate_groups(capture: Capture, work: Group, leaf: Group) -> None:
    if _identity(work) != capture.work_identity or _identity(leaf) != capture.leaf_identity:
        invalid("owned cgroup identity changed")
    if _limits(work) != capture.work_limits or _limits(leaf) != capture.leaf_limits:
        invalid("owned cgroup limits changed")
    if leaf.path.parent != work.path or _expected_membership(leaf) != capture.expected_membership:
        invalid("owned cgroup ancestry changed")


def validate(capture: Capture, work: Group, leaf: Group) -> str:
    """Return alive or exited, or fail closed on observed identity/limit drift."""
    _validate_groups(capture, work, leaf)
    if not _alive(capture.pidfd):
        return "exited"
    try:
        current = membership(capture.pid)
    except FileNotFoundError:
        if not _alive(capture.pidfd):
            return "exited"
        unavailable("live process membership is unavailable")
    if not _alive(capture.pidfd):
        return "exited"
    if current != capture.expected_membership:
        invalid("live native process left its admitted cgroup")
    return "alive"


def capture(
    work: Group,
    leaf: Group,
    pid: int,
    *,
    work_limits: LimitTriple,
    leaf_limits: LimitTriple,
) -> Capture:
    """Pin the unreaped child; validate membership after its exec handshake."""
    if work_limits[2] != "0" or leaf_limits[2] != "0":
        invalid("owned cgroups require zero swap")
    work_memory, work_tasks = int(work_limits[0]), int(work_limits[1])
    leaf_memory, leaf_tasks = int(leaf_limits[0]), int(leaf_limits[1])
    if not 0 < leaf_memory <= work_memory or not 0 < leaf_tasks <= work_tasks:
        invalid("owned cgroup limits exceed their enclosing limits")
    if leaf.path.parent != work.path:
        invalid("native leaf is not a direct child of work")
    pidfd = os.pidfd_open(pid)
    try:
        result = Capture(
            pid,
            pidfd,
            _identity(work),
            _identity(leaf),
            work_limits,
            leaf_limits,
            _expected_membership(leaf),
        )
        _validate_groups(result, work, leaf)
    except BaseException:
        os.close(pidfd)
        raise
    return result
