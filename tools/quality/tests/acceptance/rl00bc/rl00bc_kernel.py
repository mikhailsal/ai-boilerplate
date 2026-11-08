"""Bounded, descriptor-owned experimental payload execution; not a physical-RSS proof."""

from __future__ import annotations

import fcntl
import logging
import os
import re
import stat
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, save
from tests.acceptance.rl00bc import rl00bc_integrity
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid, unavailable
from tests.acceptance.rl00bc.rl00bc_kernel_launch import handshake, launch
from tests.acceptance.rl00bc.rl00bc_kernel_observe import Observation, snapshot

RESERVE_NS = 3_000_000_000


def lock_lifecycle(fd: int, deadline: int) -> None:
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if time.monotonic_ns() >= deadline:
                expired("lifecycle lock deadline")
            time.sleep(0.005)
        else:
            return


def _lifecycle() -> tuple[int, Path]:
    fd = int(os.environ["RL00_LIFECYCLE_FD"])
    closing = Path(os.environ["RL00_LIFECYCLE_CLOSING"])
    expected = int(os.environ["RL00_LIFECYCLE_INODE"])
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_ino != expected
        or not closing.is_absolute()
    ):
        invalid("invalid lifecycle authority")
    independent = os.open(f"/proc/self/fd/{fd}", os.O_RDWR | os.O_CLOEXEC)
    reopened = os.fstat(independent)
    if (reopened.st_dev, reopened.st_ino, reopened.st_uid) != (
        info.st_dev,
        info.st_ino,
        info.st_uid,
    ):
        os.close(independent)
        invalid("lifecycle descriptor identity mismatch")
    return independent, closing


def _reservations(work: Group) -> tuple[int, int]:
    with os.scandir(work.fd) as entries:
        found = list(entries)
    if any(entry.is_symlink() for entry in found):
        invalid("unexpected work child symlink")
    names = [entry.name for entry in found if entry.is_dir(follow_symlinks=False)]
    memory_used = 0
    tasks_used = 0
    for name in names:
        if re.fullmatch(r"[a-f0-9]{32}", name) is None:
            invalid("unexpected work child")
        child = work.adopt(name)
        try:
            memory = int(child.read("memory.max"))
            count = int(child.read("pids.max"))
            if memory <= 0 or count <= 0 or child.read("memory.swap.max") != "0":
                invalid("invalid work child capacity")
            memory_used += memory
            tasks_used += count
        finally:
            os.close(child.fd)
    return memory_used, tasks_used


def _admit(work: Group, memory_mib: int, tasks: int) -> dict[str, int]:
    if memory_mib <= 0 or tasks <= 0:
        invalid("invalid requested capacity")
    memory_limit = int(work.read("memory.max"))
    task_limit = int(work.read("pids.max"))
    memory_used, tasks_used = _reservations(work)
    if memory_used + memory_mib * 1024 * 1024 > memory_limit or tasks_used + tasks > task_limit:
        invalid("insufficient checker capacity")
    if int(work.read("memory.max")) != memory_limit or int(work.read("pids.max")) != task_limit:
        invalid("work capacity changed during admission")
    return {
        "memory_reserved_bytes": memory_used,
        "tasks_reserved": tasks_used,
        "memory_limit_bytes": memory_limit,
        "tasks_limit": task_limit,
    }


@dataclass
class _Execution:
    work: Group
    argv: list[str]
    cwd: Path
    env: dict[str, str]
    output: Path
    memory_mib: int
    tasks: int
    stop: int
    ancestor_deadline_ns: int
    lifecycle: int
    closing: Path
    leaf: Group | None = None
    process: subprocess.Popen[bytes] | None = None
    integrity: rl00bc_integrity.Capture | None = None
    locked: bool = True
    observation: Observation = field(default_factory=Observation)
    result: dict[str, object] = field(
        default_factory=lambda: {
            "cause": "environment-unavailable",
            "success": False,
            "native_status": None,
            "elapsed_seconds": None,
            "cpu_seconds": None,
            "memory_peak_bytes": None,
            "sampled_memory_peak_bytes": None,
            "max_tasks": None,
            "resource_sample_count": 0,
            "max_tasks_kind": "unavailable",
            "sampled_memory_peak_kind": "unavailable",
            "resource_violation": None,
            "cleanup_complete": False,
        }
    )

    def run(self) -> None:
        start = time.monotonic_ns()
        if self.closing.exists() or time.monotonic_ns() >= self.stop:
            invalid("session closing or deadline reached")
        if os.fstat(self.work.fd).st_ino != self.work.inode:
            invalid("work descriptor changed")
        admission_ns = time.monotonic_ns()
        capacity = _admit(self.work, self.memory_mib, self.tasks)
        leaf = self.work.create(uuid.uuid4().hex, self.memory_mib, self.tasks)
        self.leaf = leaf
        before, parent_before = snapshot(leaf), snapshot(self.work)
        process, integrity = self.launch_subject(leaf, capacity)
        launch_ns = time.monotonic_ns()
        fcntl.flock(self.lifecycle, fcntl.LOCK_UN)
        self.locked = False
        self.observation.capture(
            process,
            leaf,
            self.stop,
            lambda: rl00bc_integrity.validate(integrity, self.work, leaf),
        )
        self.result = self.observation.result(
            process, leaf, self.work, before, parent_before, start
        )
        self.result.update(
            {
                "launch_resolved": True,
                "launch_resolution": "exec_or_dead",
                "launch_resolved_ns": launch_ns,
                "admission_ns": admission_ns,
                "closing_absent_at_admission": True,
                "capacity_at_admission": capacity,
            }
        )

    def launch_subject(
        self, leaf: Group, capacity: dict[str, int]
    ) -> tuple[subprocess.Popen[bytes], rl00bc_integrity.Capture]:
        process, read_fd = launch(leaf, self.argv, self.cwd, self.env)
        self.process = process
        handshake_entered = False
        try:
            integrity = rl00bc_integrity.capture(
                self.work,
                leaf,
                process.pid,
                work_limits=(
                    str(capacity["memory_limit_bytes"]),
                    str(capacity["tasks_limit"]),
                    "0",
                ),
                leaf_limits=(str(self.memory_mib * 1024 * 1024), str(self.tasks), "0"),
            )
            self.integrity = integrity
            handshake_entered = True
            handshake(process, read_fd, self.stop)
        except BaseException:
            if not handshake_entered:
                os.close(read_fd)
            try:
                leaf.kill()
            except BaseException:
                logging.exception("payload handshake group kill failed")
            errors: list[str] = []
            self._reap(errors)
            raise
        return process, integrity

    def wait_timeout(self) -> float:
        return max(0.001, min(1.0, (self.ancestor_deadline_ns - time.monotonic_ns()) / 1e9))

    def _remove_leaf(self) -> None:
        if self.closing.exists():
            unavailable("guardian owns cleanup after closing")
        if self.leaf is None:
            unavailable("leaf was not created")
        errors: list[str] = []
        try:
            self.leaf.kill()
        except BaseException as error:
            logging.exception("payload group kill failed")
            errors.append(f"kill: {type(error).__name__}: {error}")
        self._reap(errors)
        try:
            self.leaf.remove()
        except BaseException as error:
            logging.exception("payload group removal failed")
            errors.append(f"remove: {type(error).__name__}: {error}")
        if errors:
            unavailable("; ".join(errors))
        absent_ns = time.monotonic_ns()
        self.result["removal_observed_ns"] = absent_ns
        self.result["cleanup_complete"] = True
        if absent_ns > self.ancestor_deadline_ns or absent_ns > self.stop + RESERVE_NS:
            expired("cleanup exceeded fixed deadline")

    def _reap(self, errors: list[str]) -> None:
        if self.process is None:
            return
        try:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=self.wait_timeout())
        except BaseException as error:
            logging.exception("payload process reap failed")
            errors.append(f"reap: {type(error).__name__}: {error}")
        finally:
            for stream in (self.process.stdout, self.process.stderr):
                if stream is not None:
                    stream.close()

    def cleanup(self) -> None:
        if self.locked:
            fcntl.flock(self.lifecycle, fcntl.LOCK_UN)
        try:
            lock_lifecycle(self.lifecycle, min(self.ancestor_deadline_ns, self.stop + RESERVE_NS))
            self._remove_leaf()
        except BaseException as error:
            logging.exception("payload cleanup failed")
            self.result["success"] = False
            self.result["cleanup_complete"] = False
            self.result["cleanup_error"] = f"{type(error).__name__}: {error}"
        finally:
            fcntl.flock(self.lifecycle, fcntl.LOCK_UN)
        try:
            for name, data in self.observation.streams.items():
                (self.output / f"{name}.log").write_bytes(data)
            save(self.output / "result.json", self.result)
        except BaseException as error:
            logging.exception("payload result persistence failed")
            self.result["success"] = False
            self.result["save_error"] = f"{type(error).__name__}: {error}"
        finally:
            if self.integrity is not None:
                self.integrity.close()
            os.close(self.lifecycle)


def execute(
    work: Group,
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    output: Path,
    *,
    memory_mib: int,
    tasks: int,
    native_seconds: float,
    ancestor_deadline_ns: int,
    payload_deadline_ns: int | None = None,
) -> dict[str, object]:
    """Run one bounded leaf, preserving failures and cleanup evidence."""
    now = time.monotonic_ns()
    if not argv or native_seconds <= 0 or now >= ancestor_deadline_ns - RESERVE_NS:
        invalid("invalid command or insufficient original deadline")
    if work.read("cgroup.procs") or not {"memory", "pids"} <= set(
        work.read("cgroup.subtree_control").split()
    ):
        invalid("work branch is not empty and delegated")
    stop = min(
        now + int(native_seconds * 1_000_000_000),
        ancestor_deadline_ns - RESERVE_NS,
        payload_deadline_ns if payload_deadline_ns is not None else ancestor_deadline_ns,
    )
    if stop <= now:
        invalid("payload deadline already expired")
    output.mkdir(parents=True, exist_ok=True)
    lifecycle, closing = _lifecycle()
    try:
        lock_lifecycle(lifecycle, stop)
    except BaseException:
        os.close(lifecycle)
        raise
    run = _Execution(
        work,
        argv,
        cwd,
        env,
        output,
        memory_mib,
        tasks,
        stop,
        ancestor_deadline_ns,
        lifecycle,
        closing,
    )
    try:
        run.run()
    except BaseException as error:
        logging.exception("payload observation failed")
        run.result["success"] = False
        run.result["cause"] = "environment-unavailable"
        run.result["observation_error"] = f"{type(error).__name__}: {error}"
    finally:
        run.cleanup()
    return run.result
