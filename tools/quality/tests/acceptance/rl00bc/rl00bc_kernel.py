"""Bounded, descriptor-owned experimental payload execution; not a physical-RSS proof."""

from __future__ import annotations

import os
import re
import fcntl
import stat
import selectors
import select
import sys
import subprocess
import time
import uuid
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, SHIM, counters, save

LIMIT = 65536
RESERVE_NS = 3_000_000_000


def _snapshot(group: Group) -> dict[str, object]:
    result = group.snapshot()
    result["cpu.stat"] = counters(group.read("cpu.stat"))
    result["pids.events.local"] = counters(group.read("pids.events.local"))
    return result


def _delta(before: dict[str, object], after: dict[str, object], field: str, key: str) -> int:
    first = before[field]
    last = after[field]
    if not isinstance(first, dict) or not isinstance(last, dict):
        raise ValueError(f"missing counter {field}")
    return int(last[key]) - int(first[key])


def _lock(fd: int, deadline: int) -> None:
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic_ns() >= deadline:
                raise TimeoutError("lifecycle lock deadline")
            time.sleep(0.005)


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
        raise ValueError("invalid lifecycle authority")
    independent = os.open(f"/proc/self/fd/{fd}", os.O_RDWR | os.O_CLOEXEC)
    reopened = os.fstat(independent)
    if (reopened.st_dev, reopened.st_ino, reopened.st_uid) != (
        info.st_dev,
        info.st_ino,
        info.st_uid,
    ):
        os.close(independent)
        raise ValueError("lifecycle descriptor identity mismatch")
    return independent, closing


def _admit(work: Group, memory_mib: int, tasks: int) -> dict[str, int]:
    if memory_mib <= 0 or tasks <= 0:
        raise ValueError("invalid requested capacity")
    memory_limit = int(work.read("memory.max"))
    task_limit = int(work.read("pids.max"))
    memory_used = 0
    tasks_used = 0
    with os.scandir(work.fd) as entries:
        found = list(entries)
    if any(entry.is_symlink() for entry in found):
        raise ValueError("unexpected work child symlink")
    names = [entry.name for entry in found if entry.is_dir(follow_symlinks=False)]
    for name in names:
        if re.fullmatch(r"[a-f0-9]{32}", name) is None:
            raise ValueError("unexpected work child")
        child = work.adopt(name)
        try:
            memory = int(child.read("memory.max"))
            count = int(child.read("pids.max"))
            if memory <= 0 or count <= 0 or child.read("memory.swap.max") != "0":
                raise ValueError("invalid work child capacity")
            memory_used += memory
            tasks_used += count
        finally:
            os.close(child.fd)
    if memory_used + memory_mib * 1024 * 1024 > memory_limit or tasks_used + tasks > task_limit:
        raise ValueError("insufficient checker capacity")
    if int(work.read("memory.max")) != memory_limit or int(work.read("pids.max")) != task_limit:
        raise ValueError("work capacity changed during admission")
    return {
        "memory_reserved_bytes": memory_used,
        "tasks_reserved": tasks_used,
        "memory_limit_bytes": memory_limit,
        "tasks_limit": task_limit,
    }


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
    """Run one bounded leaf, preserving failures and cleanup evidence.

    An observed absence time is an upper bound on removal, not its exact time.
    Missing counters, output persistence, cleanup, or causal evidence never pass.
    """
    now = time.monotonic_ns()
    if not argv or native_seconds <= 0 or now >= ancestor_deadline_ns - RESERVE_NS:
        raise ValueError("invalid command or insufficient original deadline")
    if work.read("cgroup.procs") or not {"memory", "pids"} <= set(
        work.read("cgroup.subtree_control").split()
    ):
        raise ValueError("work branch is not empty and delegated")
    stop = min(
        now + int(native_seconds * 1_000_000_000),
        ancestor_deadline_ns - RESERVE_NS,
        payload_deadline_ns if payload_deadline_ns is not None else ancestor_deadline_ns,
    )
    if stop <= now:
        raise ValueError("payload deadline already expired")
    output.mkdir(parents=True, exist_ok=True)
    lifecycle, closing = _lifecycle()
    try:
        _lock(lifecycle, stop)
    except BaseException:
        os.close(lifecycle)
        raise
    locked = True
    leaf: Group | None = None
    process: subprocess.Popen[bytes] | None = None
    result: dict[str, object] = {
        "cause": "environment-unavailable",
        "success": False,
        "native_status": None,
        "elapsed_seconds": 0.0,
        "cpu_seconds": 0.0,
        "memory_peak_bytes": None,
        "sampled_memory_peak_bytes": 0,
        "max_tasks": 0,
        "resource_violation": None,
        "cleanup_complete": False,
    }
    failure: str | None = None
    timed_out = False
    streams: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}
    selector = selectors.DefaultSelector()
    start = time.monotonic_ns()
    try:
        if closing.exists() or time.monotonic_ns() >= stop:
            raise ValueError("session closing or deadline reached")
        if os.fstat(work.fd).st_ino != work.inode:
            raise ValueError("work descriptor changed")
        admission_ns = time.monotonic_ns()
        capacity = _admit(work, memory_mib, tasks)
        leaf = work.create(uuid.uuid4().hex, memory_mib, tasks)
        before, parent_before = _snapshot(leaf), _snapshot(work)
        fd = os.open("cgroup.procs", os.O_WRONLY | os.O_NOFOLLOW, dir_fd=leaf.fd)
        read_fd, write_fd = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
        placement_shim = SHIM.replace("shift; exec", 'eval "exec $1>&-"; shift; exec')
        repo = Path(__file__).resolve().parents[5]
        try:
            process = subprocess.Popen(
                [
                    "/bin/bash",
                    "-c",
                    placement_shim,
                    "rl00bc-placement",
                    str(fd),
                    sys.executable,
                    str(Path(__file__).with_name("rl00bc_exec.py")),
                    str(write_fd),
                    str(cwd.absolute()),
                    *argv,
                ],
                cwd=repo,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(fd, write_fd),
            )
        finally:
            os.close(fd)
            os.close(write_fd)
        handshake = bytearray()
        try:
            while True:
                remaining = (stop - time.monotonic_ns()) / 1_000_000_000
                if remaining <= 0:
                    raise TimeoutError("native exec handshake deadline")
                if not select.select([read_fd], [], [], min(remaining, 0.02))[0]:
                    continue
                chunk = os.read(read_fd, 4097)
                if not chunk:
                    break
                handshake.extend(chunk)
                if len(handshake) > 4096:
                    raise ValueError("native exec handshake too large")
            if bytes(handshake) != b"ready\n":
                raise RuntimeError("native exec handshake failed")
            if process.poll() is not None:
                raise RuntimeError("native exited before exec handshake could be verified")
        except BaseException:
            # The shell might not have joined the leaf yet. Kill this owned
            # unreaped child as well as the leaf before releasing admission.
            try:
                leaf.kill()
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(
                    timeout=max(0.001, min(1.0, (ancestor_deadline_ns - time.monotonic_ns()) / 1e9))
                )
            raise
        finally:
            os.close(read_fd)
        # EOF resolves the launch: exec committed or the helper died. Native
        # producer identity is required elsewhere to establish actual execution.
        launch_resolved = True
        launch_resolved_ns = time.monotonic_ns()
        fcntl.flock(lifecycle, fcntl.LOCK_UN)
        locked = False
        assert process.stdout is not None and process.stderr is not None
        for label, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, label)
        high_memory = 0
        high_tasks = 0
        while selector.get_map() or process.poll() is None:
            if time.monotonic_ns() >= stop:
                timed_out = True
                break
            high_memory = max(high_memory, int(leaf.read("memory.current")))
            high_tasks = max(high_tasks, int(leaf.read("pids.current")))
            for key, _ in selector.select(timeout=0.02):
                chunk = os.read(key.fd, 16384)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                label = str(key.data)
                space = LIMIT - len(streams[label])
                streams[label].extend(chunk[:space])
                truncated[label] = truncated[label] or len(chunk) > space
        after, parent_after = _snapshot(leaf), _snapshot(work)
        own_memory = any(
            _delta(before, after, "memory.events.local", key) > 0 for key in ("oom", "oom_kill")
        )
        own_tasks = _delta(before, after, "pids.events.local", "max") > 0
        parent_memory = any(
            _delta(parent_before, parent_after, "memory.events.local", key) > 0
            for key in ("oom", "oom_kill")
        )
        parent_tasks = _delta(parent_before, parent_after, "pids.events.local", "max") > 0
        status = process.poll()
        cause = (
            "ancestor-resource"
            if parent_memory or parent_tasks
            else "own-memory"
            if own_memory
            else "own-tasks"
            if own_tasks
            else "timeout"
            if timed_out
            else "native-signal-unknown"
            if status is not None and status < 0
            else "native-exit"
            if status is not None
            else "environment-unavailable"
        )
        elapsed_seconds = (time.monotonic_ns() - start) / 1_000_000_000
        cpu_before = before["cpu.stat"]
        cpu_after = after["cpu.stat"]
        if not isinstance(cpu_before, dict) or not isinstance(cpu_after, dict):
            raise ValueError("missing cpu statistics")
        cpu_seconds = (int(cpu_after["usage_usec"]) - int(cpu_before["usage_usec"])) / 1_000_000
        peak_value = after["memory.peak"]
        memory_peak = int(str(peak_value)) if peak_value is not None else None
        violation = (
            cause if cause in ("own-memory", "own-tasks", "ancestor-resource", "timeout") else None
        )
        result = {
            "cause": cause,
            "success": cause == "native-exit" and status == 0,
            "native_status": status,
            "timed_out": timed_out,
            "before": before,
            "after": after,
            "work_before": parent_before,
            "work_after": parent_after,
            "sampled_memory_high_bytes": high_memory,
            "sampled_tasks_high": high_tasks,
            "elapsed_seconds": elapsed_seconds,
            "cpu_seconds": cpu_seconds,
            "memory_peak_bytes": memory_peak,
            "sampled_memory_peak_bytes": high_memory,
            "max_tasks": high_tasks,
            "resource_violation": violation,
            "cleanup_complete": False,
            "launch_resolved": launch_resolved,
            "launch_resolution": "exec_or_dead",
            "launch_resolved_ns": launch_resolved_ns,
            "admission_ns": admission_ns,
            "closing_absent_at_admission": True,
            "capacity_at_admission": capacity,
            "truncated": truncated,
        }
    except BaseException as error:
        failure = f"{type(error).__name__}: {error}"
        result["success"] = False
        result["cause"] = "environment-unavailable"
    finally:
        selector.close()
        if locked:
            fcntl.flock(lifecycle, fcntl.LOCK_UN)
        try:
            _lock(lifecycle, min(ancestor_deadline_ns, stop + RESERVE_NS))
            if closing.exists():
                fcntl.flock(lifecycle, fcntl.LOCK_UN)
                raise RuntimeError("guardian owns cleanup after closing")
            if leaf is None:
                fcntl.flock(lifecycle, fcntl.LOCK_UN)
                raise RuntimeError("leaf was not created")
            leaf.kill()
            if process is not None:
                process.wait(
                    timeout=max(0.001, min(1.0, (ancestor_deadline_ns - time.monotonic_ns()) / 1e9))
                )
            leaf.remove()
            fcntl.flock(lifecycle, fcntl.LOCK_UN)
            absent_ns = time.monotonic_ns()
            result["removal_observed_ns"] = absent_ns
            result["cleanup_complete"] = True
            if absent_ns > ancestor_deadline_ns or absent_ns > stop + RESERVE_NS:
                raise TimeoutError("cleanup exceeded fixed deadline")
        except BaseException as error:
            fcntl.flock(lifecycle, fcntl.LOCK_UN)
            result["success"] = False
            result["cleanup_complete"] = False
            result["cleanup_error"] = f"{type(error).__name__}: {error}"
        if failure is not None:
            result["observation_error"] = failure
        try:
            for name, data in streams.items():
                (output / f"{name}.log").write_bytes(data)
            save(output / "result.json", result)
        except BaseException as error:
            result["success"] = False
            result["save_error"] = f"{type(error).__name__}: {error}"
        os.close(lifecycle)
    return result
