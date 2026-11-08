"""Capture bounded output and classify resource events for one native payload."""

from __future__ import annotations

import os
import selectors
import subprocess
import time
from dataclasses import dataclass, field

from tests.acceptance.rl00a.rl00a_cgroup import Group, counters
from tests.acceptance.rl00bc.rl00bc_errors import invalid

LIMIT = 65536


def snapshot(group: Group) -> dict[str, object]:
    result = group.snapshot()
    result["cpu.stat"] = counters(group.read("cpu.stat"))
    result["pids.events.local"] = counters(group.read("pids.events.local"))
    return result


def _delta(before: dict[str, object], after: dict[str, object], field: str, key: str) -> int:
    first, last = before[field], after[field]
    if not isinstance(first, dict) or not isinstance(last, dict):
        invalid(f"missing counter {field}")
    return int(last[key]) - int(first[key])


def _cause(
    before: dict[str, object], after: dict[str, object],
    parent_before: dict[str, object], parent_after: dict[str, object],
    timed_out: bool, status: int | None,
) -> str:
    if any(_delta(parent_before, parent_after, "memory.events.local", key) > 0
           for key in ("oom", "oom_kill")) or _delta(
        parent_before, parent_after, "pids.events.local", "max"
    ) > 0:
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
    high_memory: int = 0
    high_tasks: int = 0
    timed_out: bool = False

    def capture(self, process: subprocess.Popen[bytes], leaf: Group, stop: int) -> None:
        with selectors.DefaultSelector() as selector:
            assert process.stdout is not None and process.stderr is not None
            for label, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, label)
            while selector.get_map() or process.poll() is None:
                if time.monotonic_ns() >= stop:
                    self.timed_out = True
                    break
                self.high_memory = max(self.high_memory, int(leaf.read("memory.current")))
                self.high_tasks = max(self.high_tasks, int(leaf.read("pids.current")))
                for key, _ in selector.select(timeout=0.02):
                    chunk = os.read(key.fd, 16384)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    label = str(key.data)
                    space = LIMIT - len(self.streams[label])
                    self.streams[label].extend(chunk[:space])
                    self.truncated[label] = self.truncated[label] or len(chunk) > space

    def result(
        self, process: subprocess.Popen[bytes], leaf: Group, work: Group,
        before: dict[str, object], parent_before: dict[str, object], start: int,
    ) -> dict[str, object]:
        after, parent_after = snapshot(leaf), snapshot(work)
        status = process.poll()
        cause = _cause(before, after, parent_before, parent_after, self.timed_out, status)
        cpu_before, cpu_after = before["cpu.stat"], after["cpu.stat"]
        if not isinstance(cpu_before, dict) or not isinstance(cpu_after, dict):
            invalid("missing cpu statistics")
        cpu_seconds = (int(cpu_after["usage_usec"]) - int(cpu_before["usage_usec"])) / 1_000_000
        peak = after["memory.peak"]
        violation = (
            cause if cause in ("own-memory", "own-tasks", "ancestor-resource", "timeout") else None
        )
        return {
            "cause": cause, "success": cause == "native-exit" and status == 0,
            "native_status": status, "timed_out": self.timed_out,
            "before": before, "after": after, "work_before": parent_before,
            "work_after": parent_after, "sampled_memory_high_bytes": self.high_memory,
            "sampled_tasks_high": self.high_tasks,
            "elapsed_seconds": (time.monotonic_ns() - start) / 1_000_000_000,
            "cpu_seconds": cpu_seconds,
            "memory_peak_bytes": int(str(peak)) if peak is not None else None,
            "sampled_memory_peak_bytes": self.high_memory, "max_tasks": self.high_tasks,
            "resource_violation": violation, "cleanup_complete": False, "truncated": self.truncated,
        }
