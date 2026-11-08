"""Capture bounded output and classify resource events for one native payload."""

from __future__ import annotations

import os
import selectors
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group, counters
from tests.acceptance.rl00bc.rl00bc_errors import invalid

LIMIT = 65536


def snapshot(group: Group) -> dict[str, object]:
    result = group.snapshot()
    result["cpu.stat"] = counters(group.read("cpu.stat"))
    result["pids.events.local"] = counters(group.read("pids.events.local"))
    return result


def _counter(value: object, key: str) -> int:
    if not isinstance(value, dict):
        invalid("missing counter collection")
    entry = cast(dict[str, object], value).get(key)
    if type(entry) is not int:
        invalid(f"missing integer counter {key}")
    return entry


def _delta(before: dict[str, object], after: dict[str, object], field: str, key: str) -> int:
    return _counter(after[field], key) - _counter(before[field], key)


def _cause(
    before: dict[str, object],
    after: dict[str, object],
    parent_before: dict[str, object],
    parent_after: dict[str, object],
    timed_out: bool,
    status: int | None,
) -> str:
    if (
        any(
            _delta(parent_before, parent_after, "memory.events.local", key) > 0
            for key in ("oom", "oom_kill")
        )
        or _delta(parent_before, parent_after, "pids.events.local", "max") > 0
    ):
        return "ancestor-resource"
    if any(_delta(before, after, "memory.events.local", key) > 0 for key in ("oom", "oom_kill")):
        return "own-memory"
    if _delta(before, after, "pids.events.local", "max") > 0:
        return "own-tasks"
    if timed_out:
        return "timeout"
    if status is None:
        return "environment-unavailable"
    return "native-signal-unknown" if status < 0 else "native-exit"


@dataclass
class Observation:
    """Output buffers and sampled high-water marks for one child."""

    streams: dict[str, bytearray] = field(
        default_factory=lambda: {"stdout": bytearray(), "stderr": bytearray()}
    )
    truncated: dict[str, bool] = field(default_factory=lambda: {"stdout": False, "stderr": False})
    high_memory: int | None = None
    high_tasks: int | None = None
    resource_sample_count: int = 0
    timed_out: bool = False
    leader_state: str = "unobserved"

    def _sample(self, leaf: Group) -> None:
        memory_sample = int(leaf.read("memory.current"))
        task_sample = int(leaf.read("pids.current"))
        self.high_memory = (
            memory_sample if self.high_memory is None else max(self.high_memory, memory_sample)
        )
        self.high_tasks = (
            task_sample if self.high_tasks is None else max(self.high_tasks, task_sample)
        )
        self.resource_sample_count += 1

    def capture(
        self, process: subprocess.Popen[bytes], leaf: Group, stop: int, integrity: Callable[[], str]
    ) -> None:
        with selectors.DefaultSelector() as selector:
            assert process.stdout is not None and process.stderr is not None
            for label, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, label)
            while selector.get_map() or process.poll() is None:
                self.leader_state = integrity()
                if time.monotonic_ns() >= stop:
                    self.timed_out = True
                    break
                self._sample(leaf)
                for key, _ in selector.select(timeout=0.02):
                    chunk = os.read(key.fd, 16384)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    label = str(key.data)
                    space = LIMIT - len(self.streams[label])
                    self.streams[label].extend(chunk[:space])
                    self.truncated[label] = self.truncated[label] or len(chunk) > space
        self.leader_state = integrity()

    def result(
        self,
        process: subprocess.Popen[bytes],
        leaf: Group,
        work: Group,
        before: dict[str, object],
        parent_before: dict[str, object],
        start: int,
    ) -> dict[str, object]:
        after, parent_after = snapshot(leaf), snapshot(work)
        status = process.poll()
        cause = _cause(before, after, parent_before, parent_after, self.timed_out, status)
        cpu_seconds = _delta(before, after, "cpu.stat", "usage_usec") / 1_000_000
        peak = after["memory.peak"]
        violation = (
            cause if cause in ("own-memory", "own-tasks", "ancestor-resource", "timeout") else None
        )
        return {
            "cause": cause,
            "success": cause == "native-exit" and status == 0,
            "native_status": status,
            "leader_integrity_last_state": self.leader_state,
            "timed_out": self.timed_out,
            "before": before,
            "after": after,
            "work_before": parent_before,
            "work_after": parent_after,
            "sampled_memory_high_bytes": self.high_memory,
            "sampled_tasks_high": self.high_tasks,
            "resource_sample_count": self.resource_sample_count,
            "elapsed_seconds": (time.monotonic_ns() - start) / 1_000_000_000,
            "cpu_seconds": cpu_seconds,
            "memory_peak_bytes": int(str(peak)) if peak is not None else None,
            "memory_peak_kind": "kernel-peak" if peak is not None else "unavailable",
            "sampled_memory_peak_bytes": self.high_memory,
            "sampled_memory_peak_kind": (
                "sampled-lower-bound" if self.resource_sample_count else "unavailable"
            ),
            "max_tasks": self.high_tasks,
            "max_tasks_kind": (
                "sampled-lower-bound" if self.resource_sample_count else "unavailable"
            ),
            "resource_violation": violation,
            "cleanup_complete": False,
            "truncated": self.truncated,
        }
