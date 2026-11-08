"""Bounded test-only coordination for a real guardian lifecycle race."""

from __future__ import annotations

import fcntl
import os
import stat
import time
from pathlib import Path
from typing import Protocol

from tests.acceptance.rl00a.rl00a_cgroup import CGROUP, Group, load, save
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid


class Guardian(Protocol):
    output: Path
    deadline: int
    guardian_lock: int
    inode: int
    work: Group | None
    record: dict[str, object]
    cleanup_deadline_ns: int | None

    def begin_cleanup(self, reason: str) -> None: ...
    def publish_closing(self) -> bool: ...
    def register_work(self) -> None: ...


def locks(output: Path) -> tuple[int, int, int]:
    """Create independently opened, private descriptors for one service."""
    guardian = os.open(
        output / "lifecycle.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    try:
        controller = os.open(output / "lifecycle.lock", os.O_RDWR | os.O_NOFOLLOW)
    except BaseException:
        os.close(guardian)
        raise
    info = os.fstat(guardian)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600 or os.fstat(controller).st_ino != info.st_ino):
        os.close(guardian)
        os.close(controller)
        invalid("invalid lifecycle lock")
    return guardian, controller, info.st_ino


def wait_file(path: Path, deadline: int) -> None:
    """Wait only within the inherited fixed deadline."""
    while not path.is_file():
        if time.monotonic_ns() >= deadline:
            expired(f"race observation deadline waiting for {path.name}")
        time.sleep(0.002)


def _registered(guardian: Guardian) -> None:
    if guardian.work is not None:
        return
    wait_file(guardian.output / "work-registration.json", _start_deadline(guardian))
    guardian.register_work()


def _start_deadline(guardian: Guardian) -> int:
    return min(guardian.deadline - 3_000_000_000, time.monotonic_ns() + 10_000_000_000)


def _marker(guardian: Guardian) -> dict[str, object]:
    assert guardian.work is not None
    value = load(guardian.output / "race-marker.json")
    group = value.get("cgroup")
    prefix = "/" + str(guardian.work.path.relative_to(CGROUP)) + "/"
    if not isinstance(group, str) or not group.startswith(prefix):
        invalid("race native marker is outside the owned work branch")
    name = group[len(prefix):]
    if len(name) != 32 or any(char not in "0123456789abcdef" for char in name):
        invalid("race native marker has an invalid leaf name")
    leaf = guardian.work.adopt(name)
    try:
        pid = value.get("pid")
        if type(pid) is not int or str(pid) not in leaf.read("cgroup.procs").split():
            invalid("race native marker process is not in its owned leaf")
        return {**value, "leaf_inode": leaf.inode, "leaf_path": str(leaf.path)}
    finally:
        os.close(leaf.fd)


def _launch_first(guardian: Guardian) -> None:
    wait_file(guardian.output / "race-handshake-held.json", _start_deadline(guardian))
    held = load(guardian.output / "race-handshake-held.json")
    if held.get("lifecycle_inode") != guardian.inode:
        invalid("handshake gate used the wrong lifecycle lock")
    guardian.begin_cleanup("controller-stop")
    assert guardian.cleanup_deadline_ns is not None
    try:
        fcntl.flock(guardian.guardian_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        attempt = {"state": "blocked", "observed_ns": time.monotonic_ns()}
    else:
        fcntl.flock(guardian.guardian_lock, fcntl.LOCK_UN)
        invalid("guardian closing lock did not block behind the actual launcher")
    guardian.record["race_closing_lock_attempt"] = attempt
    save(guardian.output / "race-release.json", {"released_ns": time.monotonic_ns()})
    wait_file(guardian.output / "race-marker.json", guardian.cleanup_deadline_ns)
    native = _marker(guardian)
    if native.get("pid") != held.get("pid"):
        invalid("native marker does not identify the gated launcher process")
    guardian.record["race_handshake_held"] = held
    guardian.record["race_native_marker"] = native
    guardian.record["race_native_wait_status"] = None
    guardian.record["race_native_wait_status_reason"] = "native process is not the guardian's child"
    guardian.record["closing_published"] = guardian.publish_closing()


def _closing_first(guardian: Guardian) -> None:
    wait_file(guardian.output / "race-controller-ready.json", _start_deadline(guardian))
    guardian.begin_cleanup("controller-stop")
    assert guardian.cleanup_deadline_ns is not None
    guardian.record["closing_published"] = guardian.publish_closing()
    save(guardian.output / "race-release.json", {"released_ns": time.monotonic_ns()})
    wait_file(guardian.output / "race-controller-done.json", guardian.cleanup_deadline_ns)
    guardian.record["race_controller_result"] = load(guardian.output / "race-controller-done.json")


def watch(guardian: Guardian, race: str) -> None:
    """Run a single race in its own unit; never reuse a live multiprobe session."""
    _registered(guardian)
    guardian.record["stop_reason"] = "race-probe"
    if race == "launch-first":
        _launch_first(guardian)
    elif race == "closing-first":
        _closing_first(guardian)
    else:
        invalid("unknown guardian race")
