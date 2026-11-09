"""Unassisted observation window and expected-outcome oracle for bounded faults."""

from __future__ import annotations

import signal
import time

from tests.acceptance.rl00a.rl00a_cgroup import load
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_faults_subject import Subject, alive
from tests.acceptance.rl00bc.rl00bc_lifecycle_support import Worker

WINDOW_NS = 3_000_000_000


def _sample(subject: Subject, observation: dict[str, object]) -> None:
    if observation.get("requester_stopped_ns") is None and not alive(subject.worker_fd):
        observation["requester_stopped_ns"] = time.monotonic_ns()
        observation["requester_native_status"] = subject.worker.process.poll()
    if observation.get("native_stopped_ns") is None and not alive(subject.native_fd):
        observation["native_stopped_ns"] = time.monotonic_ns()
    if observation.get("leaf_absent_ns") is None and not subject.leaf_present():
        observation["leaf_absent_ns"] = time.monotonic_ns()


def observe_window(subject: Subject, fired: int) -> dict[str, object]:
    deadline = min(fired + WINDOW_NS, subject.deadline - WINDOW_NS)
    observation: dict[str, object] = {
        "fault_attempted_ns": fired,
        "window_deadline_ns": deadline,
        "requester_stopped_ns": None,
        "requester_native_status": None,
        "native_stopped_ns": None,
        "leaf_absent_ns": None,
        "cleanup_scope": "requester, native child and original leaf; fixture target excluded",
    }
    try:
        if deadline <= fired:
            invalid("original deadline leaves no unassisted observation window")
        while time.monotonic_ns() < deadline:
            _sample(subject, observation)
            if all(
                observation[key] is not None
                for key in ("requester_stopped_ns", "native_stopped_ns", "leaf_absent_ns")
            ):
                break
            time.sleep(0.01)
    except (OSError, ValueError, RuntimeError, AssertionError) as error:
        observation["observation_error"] = f"{type(error).__name__}: {error}"
        pause_until(deadline)
    observation["verdict_observed_ns"] = time.monotonic_ns()
    observation["automatic_cleanup_observed"] = "observation_error" not in observation and all(
        _in_window(observation.get(key), deadline)
        for key in ("requester_stopped_ns", "native_stopped_ns", "leaf_absent_ns")
    )
    return observation


def _in_window(value: object, deadline: int) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value <= deadline


def kernel_record(worker: Worker) -> dict[str, object] | None:
    path = worker.root / "kernel" / "result.json"
    return load(path) if path.is_file() else None


def worker_record(worker: Worker) -> dict[str, object] | None:
    path = worker.path("result")
    return load(path) if path.is_file() else None


def expected_outcome(
    kind: str, observation: dict[str, object], raw: dict[str, object] | None
) -> bool:
    if observation.get("automatic_cleanup_observed") is not True:
        return False
    status = observation.get("requester_native_status")
    if kind == "requester-sigkill":
        return status == -signal.SIGKILL
    if status != 0 or raw is None:
        return False
    message = "limits changed" if kind == "limit-drift" else "left its admitted cgroup"
    return (
        raw.get("success") is False
        and raw.get("cleanup_complete") is True
        and message in str(raw.get("observation_error"))
    )


def pause_until(deadline: int) -> None:
    while time.monotonic_ns() < deadline:
        remaining = max(0.0, (deadline - time.monotonic_ns()) / 1_000_000_000)
        time.sleep(min(0.01, remaining))
