"""Bounded real-kernel lifecycle probes; this is not a guardian-race proof."""

from __future__ import annotations

import fcntl
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, load, save
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_lifecycle_support import (
    Worker,
    children,
    marker,
    require_clean,
    require_marker_result,
    start,
    until,
)

MIB = 1024 * 1024
PENDING = (
    "guardian-launch-before-closing",
    "guardian-closing-before-launch",
    "abrupt-worker-death-recovery",
    "two-level-deterministic-parent-shares",
    "dying-groups-and-residual-charges",
    "membership-drift-injection",
    "limit-drift-injection",
)


@dataclass
class _Proof:
    work: Group
    repo: Path
    output: Path
    environment: dict[str, str]
    deadline: int
    initial: list[str]
    workers: list[Worker] = field(default_factory=list[Worker])
    cases: dict[str, object] = field(default_factory=dict[str, object])

    def launch(
        self,
        name: str,
        memory: int,
        tasks: int,
        deadline: int | None = None,
        *,
        hold_lock: bool = False,
    ) -> Worker:
        bound = self.deadline if deadline is None else min(self.deadline, deadline)
        worker = start(
            self.work,
            self.repo,
            self.output / name,
            self.environment,
            memory_mib=memory,
            tasks=tasks,
            deadline=bound,
            payload_deadline=bound + 60_000_000_000,
            hold_lock=hold_lock,
        )
        self.workers.append(worker)
        return worker

    def observation_deadline(self, seconds: int = 8) -> int:
        return min(self.deadline - 3_000_000_000, time.monotonic_ns() + seconds * 1_000_000_000)

    def independent_callers(self) -> None:
        first = self.launch("independent-a", 128, 8, hold_lock=True)
        until(first.path("held").is_file, self.observation_deadline())
        second = self.launch("independent-b", 128, 8)
        until(second.path("attempt").is_file, self.observation_deadline())
        attempt = load(second.path("attempt"))
        if attempt.get("state") != "blocked" or second.path("marker").exists():
            invalid("second caller did not block on the first caller's admission lock")
        first.path("proceed").touch()
        until(
            lambda: first.path("marker").is_file() and second.path("marker").is_file(),
            self.observation_deadline(),
        )
        markers = [marker(item, self.work) for item in (first, second)]
        for item in (first, second):
            item.release()
        for item, native in zip((first, second), markers, strict=True):
            item.wait(self.observation_deadline())
            result = item.result()
            if result.get("success") is not True:
                invalid("independent caller did not complete")
            require_marker_result(native, result)
        require_clean(self.work, self.initial)
        self.cases["independent-callers"] = {
            "first_held": load(first.path("held")),
            "second_attempt": attempt,
            "markers": markers,
            "results": [first.result(), second.result()],
        }

    def _waiting_pair(self, workers: tuple[Worker, Worker], lock: int) -> int:
        until(
            lambda: all(item.path("attempt").is_file() for item in workers),
            self.observation_deadline(),
        )
        attempts = [load(item.path("attempt")) for item in workers]
        if any(item.get("state") != "blocked" for item in attempts):
            invalid("independent admission did not block on held lifecycle lock")
        if any(item.path("marker").exists() for item in workers):
            invalid("native payload started while lifecycle lock was held")
        fcntl.flock(lock, fcntl.LOCK_UN)
        return time.monotonic_ns()

    def pair(self, name: str, memory: int, tasks: int) -> None:
        inherited = int(os.environ["RL00_LIFECYCLE_FD"])
        lock = os.open(f"/proc/self/fd/{inherited}", os.O_RDWR | os.O_CLOEXEC)
        locked = False
        try:
            identity = os.fstat(lock)
            if (
                identity.st_ino != int(os.environ["RL00_LIFECYCLE_INODE"])
                or identity.st_uid != os.getuid()
            ):
                invalid("lifecycle lock authority changed")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            held_ns = time.monotonic_ns()
            first = self.launch(f"{name}-a", memory, tasks)
            second = self.launch(f"{name}-b", memory, tasks)
            workers = (first, second)
            unlocked_ns = self._waiting_pair(workers, lock)
            locked = False
        finally:
            if locked:
                fcntl.flock(lock, fcntl.LOCK_UN)
            os.close(lock)
        self._complete_pair(name, workers, memory, tasks, (held_ns, unlocked_ns))

    def _complete_pair(
        self,
        name: str,
        workers: tuple[Worker, Worker],
        memory: int,
        tasks: int,
        lock_times: tuple[int, int],
    ) -> None:
        winner, loser = self._pair_outcome(workers)
        rejected = loser.result()
        if rejected.get("success") is not False or "insufficient checker capacity" not in str(
            rejected.get("observation_error")
        ):
            invalid("overcommitted concurrent admission was not rejected")
        if loser.path("marker").exists():
            invalid("rejected admission executed a native payload")
        native_marker = marker(winner, self.work)
        winner.release()
        winner.wait(self.observation_deadline())
        loser.wait(self.observation_deadline())
        admitted = winner.result()
        if admitted.get("success") is not True or admitted.get("cleanup_complete") is not True:
            invalid("admitted concurrent payload did not complete and clean up")
        require_marker_result(native_marker, admitted)
        require_clean(self.work, self.initial)
        self.cases[name] = {
            "attempts": [load(item.path("attempt")) for item in workers],
            "native_marker": native_marker,
            "admitted": admitted,
            "rejected": rejected,
            "memory_mib_per_request": memory,
            "tasks_per_request": tasks,
            "lock_held_observed_ns": lock_times[0],
            "lock_released_observed_ns": lock_times[1],
        }

    def _pair_outcome(self, workers: tuple[Worker, Worker]) -> tuple[Worker, Worker]:
        first, second = workers

        def ready() -> bool:
            if first.path("marker").exists() and second.path("marker").exists():
                invalid("two overcommitted payloads were admitted")
            return (
                (first.path("marker").is_file()
                and second.path("result").is_file())
                or (second.path("marker").is_file()
                and first.path("result").is_file())
            )

        until(ready, self.observation_deadline())
        return (first, second) if first.path("marker").is_file() else (second, first)

    def reject(self, name: str, memory: int, tasks: int) -> None:
        worker = self.launch(name, memory, tasks)
        worker.wait(self.observation_deadline())
        result = worker.result()
        if result.get("success") is not False or "insufficient checker capacity" not in str(
            result.get("observation_error")
        ):
            invalid("above-ancestor capacity was not rejected")
        if worker.path("marker").exists():
            invalid("above-ancestor request ran a native payload")
        require_clean(self.work, self.initial)
        self.cases[name] = {"result": result, "native_marker_absent": True}

    def cooperative_cancel(self) -> None:
        worker = self.launch("cancel", 128, 8)
        until(worker.path("marker").is_file, self.observation_deadline())
        native = marker(worker, self.work)
        worker.cancel()
        worker.wait(self.observation_deadline())
        result = worker.result()
        if (
            result.get("success") is not False
            or result.get("cleanup_complete") is not True
            or "KeyboardInterrupt" not in str(result.get("observation_error"))
        ):
            invalid("cooperative cancellation did not retain failure and clean up")
        require_clean(self.work, self.initial)
        self.cases["cooperative-cancel"] = {"marker": native, "result": result}
        self.recovery()

    def recovery(self) -> None:
        worker = self.launch("recovery", 128, 8)
        until(worker.path("marker").is_file, self.observation_deadline())
        native = marker(worker, self.work)
        worker.release()
        worker.wait(self.observation_deadline())
        result = worker.result()
        if result.get("success") is not True or result.get("cleanup_complete") is not True:
            invalid("capacity was not recovered after cancellation")
        require_marker_result(native, result)
        require_clean(self.work, self.initial)
        self.cases["recovery"] = {"marker": native, "result": result}

    def deadline_probe(self) -> None:
        child_deadline = min(self.deadline - 1_000_000_000, time.monotonic_ns() + 8_000_000_000)
        if child_deadline - time.monotonic_ns() < 6_000_000_000:
            invalid("insufficient original deadline for bounded deadline probe")
        worker = self.launch("deadline", 128, 8, child_deadline)
        until(
            worker.path("marker").is_file,
            min(child_deadline - 3_000_000_000, self.observation_deadline()),
        )
        native = marker(worker, self.work)
        worker.wait(child_deadline)
        observed = time.monotonic_ns()
        result = worker.result()
        removed = result.get("removal_observed_ns")
        if (
            result.get("cause") != "timeout"
            or result.get("cleanup_complete") is not True
            or not isinstance(removed, int)
            or removed > child_deadline
            or observed > child_deadline
        ):
            invalid("later requested deadline extended or defeated original deadline")
        require_marker_result(native, result)
        require_clean(self.work, self.initial)
        self.cases["deadline-clamped"] = {
            "original_deadline_ns": child_deadline,
            "requested_payload_deadline_ns": child_deadline + 60_000_000_000,
            "completed_observed_ns": observed,
            "marker": native,
            "result": result,
        }

    def expired_entry(self) -> None:
        worker = self.launch("expired-entry", 128, 8, time.monotonic_ns() + 1_000_000_000)
        worker.wait(self.observation_deadline())
        result = worker.result()
        if "insufficient original deadline" not in str(result.get("raised")):
            invalid("already exhausted enclosing deadline was not rejected")
        if worker.path("marker").exists() or worker.path("attempt").exists():
            invalid("expired request reached admission or native execution")
        require_clean(self.work, self.initial)
        self.cases["expired-entry"] = {"result": result, "native_marker_absent": True}

    def stop_workers(self) -> list[str]:
        errors: list[str] = []
        for worker in self.workers:
            try:
                worker.stop(self.deadline)
            except (OSError, subprocess.SubprocessError) as error:
                errors.append(f"{worker.root.name}: {type(error).__name__}: {error}")
        return errors


def _record(output: Path, result: dict[str, object]) -> None:
    save(output / "lifecycle.json", result)


def _limits(work: Group) -> tuple[int, int]:
    memory = int(work.read("memory.max")) // MIB
    tasks = int(work.read("pids.max"))
    if memory < 512 or tasks < 32 or work.read("memory.swap.max") != "0":
        invalid("insufficient finite work capacity for lifecycle probes")
    return memory, tasks


def _exercise(proof: _Proof, result: dict[str, object], memory: int, tasks: int) -> None:
    stages = (
        ("independent-callers", proof.independent_callers),
        ("concurrent-memory", lambda: proof.pair("concurrent-memory", memory // 2 + 1, 8)),
        ("concurrent-tasks", lambda: proof.pair("concurrent-tasks", 128, tasks // 2 + 1)),
        ("above-memory", lambda: proof.reject("above-memory", memory + 1, 8)),
        ("above-tasks", lambda: proof.reject("above-tasks", 128, tasks + 1)),
        ("cooperative-cancel", proof.cooperative_cancel),
        ("deadline-clamped", proof.deadline_probe),
        ("expired-entry", proof.expired_entry),
    )
    for name, action in stages:
        result["active_case"] = name
        proof.cases[name] = {"status": "in-progress"}
        _record(proof.output, result)
        action()
        _record(proof.output, result)


def _finalize(proof: _Proof, result: dict[str, object]) -> None:
    cleanup_errors = proof.stop_workers()
    result["worker_cleanup_errors"] = cleanup_errors
    try:
        result["final_work_children"] = children(proof.work)
    except OSError as error:
        cleanup_errors.append(f"work observation: {type(error).__name__}: {error}")
    if cleanup_errors or result.get("final_work_children") != proof.initial:
        result["status"] = "nonpass"
    try:
        _record(proof.output, result)
    except OSError as error:
        result["status"] = "nonpass"
        result["persistence_error"] = f"{type(error).__name__}: {error}"


def check(
    work: Group,
    repo: Path,
    scratch: Path,
    output: Path,
    environment: dict[str, str],
    *,
    ancestor_deadline_ns: int,
) -> dict[str, object]:
    """Collect bounded observations without modifying the live guardian closing marker."""
    output.mkdir(parents=True, exist_ok=False)
    initial = children(work)
    cases: dict[str, object] = {}
    result: dict[str, object] = {
        "status": "in-progress",
        "success": False,
        "cases": cases,
        "required_proofs_pending": list(PENDING),
        "original_deadline_ns": ancestor_deadline_ns,
        "scratch": str(scratch),
        "initial_work_children": initial,
        "lock_probe": "independent reopen and real nonblocking flock before real admission lock",
        "scope": "sibling admission and cooperative interruption; not a real guardian race",
    }
    _record(output, result)
    proof = _Proof(work, repo, output, environment, ancestor_deadline_ns, initial, cases=cases)
    try:
        if initial:
            invalid("lifecycle proof requires an otherwise idle work branch")
        memory, tasks = _limits(work)
        result["work_limits"] = {"memory_mib": memory, "tasks": tasks, "swap": 0}
        _exercise(proof, result, memory, tasks)
        result["status"] = "observed-partial"
        result.pop("active_case", None)
    except (
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
        KeyError,
        AssertionError,
        subprocess.SubprocessError,
    ) as error:
        result["status"] = "nonpass"
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        _finalize(proof, result)
    return result
