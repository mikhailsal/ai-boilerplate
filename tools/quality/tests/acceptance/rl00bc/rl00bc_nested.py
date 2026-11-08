"""Real two-parent nested-capacity observations; never a complete RL00b verdict."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, save
from tests.acceptance.rl00bc import rl00bc_nested_cases as cases
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_nested_process import require_success, wait_until
from tests.acceptance.rl00bc.rl00bc_nested_protocol import Protocol
from tests.acceptance.rl00bc.rl00bc_nested_scope import (
    DOMAIN_MEMORY, DOMAIN_TASKS, PARENT_MEMORY, PARENT_TASKS, POOL_MEMORY, POOL_TASKS, Scope,
)

PENDING = (
    "outer-original-root-removal-and-independent-sentinel",
    "guardian-launch-closing-orders",
    "abrupt-controller-death-recovery",
    "membership-and-limit-drift-injection",
    "dying-groups-and-residual-charges",
    "general-deterministic-scheduler-and-all-native-worker-configurations",
)


def _write(output: Path, record: dict[str, object]) -> None:
    save(output / "nested.json", record)


def _expected_requests() -> list[dict[str, object]]:
    return [
        {"kind": "concurrent", "memory_mib": 64, "tasks": 8, "expected": "success"},
        {"kind": "over-memory", "memory_mib": POOL_MEMORY + 1, "tasks": 8,
         "expected": "rejected-before-native"},
        {"kind": "over-tasks", "memory_mib": 64, "tasks": POOL_TASKS + 1,
         "expected": "rejected-before-native"},
        {"kind": "cancel", "memory_mib": 64, "tasks": 8, "expected": "interrupt-and-cleanup"},
        {"kind": "recovery", "memory_mib": 64, "tasks": 8, "expected": "success"},
        {"kind": "deadline", "memory_mib": 64, "tasks": 8, "expected": "timeout-and-cleanup"},
    ]


def _setup(scope: Scope, protocol: Protocol, record: dict[str, object]) -> None:
    if (POOL_MEMORY + 1 > DOMAIN_MEMORY - PARENT_MEMORY
            or POOL_TASKS + 1 > DOMAIN_TASKS - PARENT_TASKS):
        invalid("oversized pool probes must still fit in the enclosing parent remainder")
    scope.allocate()
    if len(scope.domains) != 2 or scope.domains[0].group.inode == scope.domains[1].group.inode:
        invalid("nested proof did not allocate two distinct domains")
    record["enclosing_work_limits"] = scope.work_limits
    record["domains"] = [domain.group.snapshot() for domain in scope.domains]
    for domain in scope.domains:
        protocol.start_parent(domain)
    protocol.assert_parents_live()
    record["parent_identities"] = [parent.identity for parent in protocol.parents]
    _write(protocol.output, record)


def _run_cases(protocol: Protocol, record: dict[str, object]) -> None:
    observations: dict[str, object] = {}
    record["cases"] = observations
    stages = (
        ("concurrent", lambda: cases.ordinary(protocol, 0, "concurrent")),
        ("over-memory", lambda: cases.reject(protocol, 1, "over-memory", POOL_MEMORY + 1, 8)),
        ("over-tasks", lambda: cases.reject(protocol, 2, "over-tasks", 64, POOL_TASKS + 1)),
        ("cancel", lambda: cases.cancel(protocol)),
        ("recovery", lambda: cases.ordinary(protocol, 4, "recovery")),
        ("deadline", lambda: cases.deadline(protocol)),
    )
    for name, action in stages:
        record["active_case"] = name
        observations[name] = {"status": "in-progress"}
        _write(protocol.output, record)
        observations[name] = action()
        _write(protocol.output, record)
    record.pop("active_case", None)


def _finish_parents(protocol: Protocol, record: dict[str, object]) -> None:
    results: list[dict[str, object]] = []
    for parent in protocol.parents:
        wait_until((parent.mailbox / "completed.json").is_file, protocol.parent_stop)
        result = parent.worker.wait(protocol.deadline)
        require_success(result)
        cases.match_result(parent.identity, result)
        results.append(result)
    record["parent_results"] = results
    record["parents_completed_ns"] = time.monotonic_ns()


def _stop_workers(protocol: Protocol) -> list[str]:
    errors: list[str] = []
    for worker in protocol.workers:
        try:
            worker.stop(protocol.deadline)
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f"{worker.output.name}: {type(error).__name__}: {error}")
    return errors


def _finish(scope: Scope, protocol: Protocol, record: dict[str, object]) -> None:
    errors = _stop_workers(protocol)
    for parent in protocol.parents:
        try:
            os.close(parent.pidfd)
        except OSError as error:
            errors.append(f"parent pidfd: {type(error).__name__}: {error}")
    try:
        errors.extend(scope.cleanup())
    except (OSError, ValueError, RuntimeError, AssertionError) as error:
        errors.append(f"scope cleanup: {type(error).__name__}: {error}")
    record["cleanup_errors"] = errors
    record["domain_absent_observed_ns"] = scope.removed_ns
    record["finished_ns"] = time.monotonic_ns()
    if errors or time.monotonic_ns() >= protocol.deadline:
        record["status"] = "nonpass"
    try:
        _write(protocol.output, record)
    except OSError as error:
        record["status"] = "nonpass"
        record["persistence_error"] = f"{type(error).__name__}: {error}"


def check(
    work: Group, repo: Path, scratch: Path, output: Path, environment: dict[str, str], *,
    ancestor_deadline_ns: int,
) -> dict[str, object]:
    """Exercise only fixed sibling shares under an inherited absolute deadline."""
    output.mkdir(parents=True, exist_ok=False)
    deadline = min(ancestor_deadline_ns, time.monotonic_ns() + 60_000_000_000)
    parent_stop = deadline - 3_000_000_000
    scope = Scope(work, deadline)
    protocol = Protocol(scope, repo, output, environment, deadline, parent_stop, 0, 0)
    record: dict[str, object] = {
        "status": "in-progress", "success": False, "original_deadline_ns": ancestor_deadline_ns,
        "proof_deadline_ns": deadline, "parent_stop_ns": parent_stop, "scratch": str(scratch),
        "shares": {"domain_mib": DOMAIN_MEMORY, "domain_tasks": DOMAIN_TASKS,
                   "parent_mib": PARENT_MEMORY, "parent_tasks": PARENT_TASKS,
                   "pool_mib": POOL_MEMORY, "pool_tasks": POOL_TASKS},
        "expected_requests_per_parent": _expected_requests(),
        "rejection_bound_ns": 3_000_000_000,
        "required_proofs_pending": list(PENDING),
    }
    _write(output, record)
    try:
        lock_info = os.fstat(int(os.environ["RL00_LIFECYCLE_FD"]))
        protocol.lock_dev, protocol.lock_ino = lock_info.st_dev, lock_info.st_ino
        if parent_stop - time.monotonic_ns() < 20_000_000_000:
            invalid("insufficient inherited deadline for nested proof")
        _setup(scope, protocol, record)
        _run_cases(protocol, record)
        _finish_parents(protocol, record)
        record["status"] = "observed-partial"
    except (OSError, ValueError, TypeError, RuntimeError, KeyError, AssertionError,
            subprocess.SubprocessError) as error:
        record["status"] = "nonpass"
        record["error"] = f"{type(error).__name__}: {error}"
    finally:
        _finish(scope, protocol, record)
    return record
