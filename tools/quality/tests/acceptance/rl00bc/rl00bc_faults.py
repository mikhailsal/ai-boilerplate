"""Bounded fault observations before any manually assisted safety cleanup."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, load, save
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_faults_actions import (
    create_target,
    kill_requester,
    lower_limit,
    manual_cleanup,
    move_native,
    stop_unbound,
)
from tests.acceptance.rl00bc.rl00bc_faults_subject import (
    Subject,
    alive,
    controller_identity,
    identity,
    open_subject,
    work_entry,
)
from tests.acceptance.rl00bc.rl00bc_lifecycle_support import Worker, start

WINDOW_NS = 3_000_000_000
PENDING = (
    "outer-original-root-removal-and-independent-sentinel",
    "guardian-death-and-controller-death-full-matrix",
    "unobserved-drift-windows-and-all-descendant-membership",
    "uninterruptible-kernel-state-and-scheduling-bounds",
)


def _write(output: Path, record: dict[str, object]) -> None:
    save(output / "faults.json", record)


def _fault(subject: Subject, kind: str) -> int:
    if time.monotonic_ns() >= subject.deadline - 8_000_000_000:
        invalid("insufficient original deadline for an unassisted fault window")
    if kind == "requester-sigkill":
        return kill_requester(subject)
    if kind == "limit-drift":
        return lower_limit(subject)
    if kind == "membership-drift":
        return move_native(subject)
    invalid("unknown bounded fault case")


def _sample(subject: Subject, observation: dict[str, object]) -> None:
    if observation.get("requester_stopped_ns") is None and not alive(subject.worker_fd):
        observation["requester_stopped_ns"] = time.monotonic_ns()
        observation["requester_native_status"] = subject.worker.process.poll()
    if observation.get("native_stopped_ns") is None and not alive(subject.native_fd):
        observation["native_stopped_ns"] = time.monotonic_ns()
    if observation.get("leaf_absent_ns") is None and not subject.leaf_present():
        observation["leaf_absent_ns"] = time.monotonic_ns()


def _observe(subject: Subject, fired: int) -> dict[str, object]:
    deadline = min(fired + WINDOW_NS, subject.deadline - WINDOW_NS)
    observation: dict[str, object] = {
        "fault_attempted_ns": fired, "window_deadline_ns": deadline,
        "requester_stopped_ns": None, "requester_native_status": None,
        "native_stopped_ns": None, "leaf_absent_ns": None,
        "cleanup_scope": "requester, native child and original leaf; fixture target excluded",
    }
    try:
        if deadline <= fired:
            invalid("original deadline leaves no unassisted observation window")
        while time.monotonic_ns() < deadline:
            _sample(subject, observation)
            if all(observation[key] is not None for key in
                   ("requester_stopped_ns", "native_stopped_ns", "leaf_absent_ns")):
                break
            time.sleep(0.01)
    except (OSError, ValueError, RuntimeError, AssertionError) as error:
        observation["observation_error"] = f"{type(error).__name__}: {error}"
        _pause_until(deadline)
    observation["verdict_observed_ns"] = time.monotonic_ns()
    observation["automatic_cleanup_observed"] = "observation_error" not in observation and all(
        _in_window(observation.get(key), deadline)
        for key in ("requester_stopped_ns", "native_stopped_ns", "leaf_absent_ns")
    )
    return observation


def _in_window(value: object, deadline: int) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value <= deadline


def _kernel_record(worker: Worker) -> dict[str, object] | None:
    path = worker.root / "kernel" / "result.json"
    return load(path) if path.is_file() else None


def _worker_record(worker: Worker) -> dict[str, object] | None:
    path = worker.path("result")
    return load(path) if path.is_file() else None


def _expected(kind: str, observation: dict[str, object], raw: dict[str, object] | None) -> bool:
    if observation.get("automatic_cleanup_observed") is not True:
        return False
    status = observation.get("requester_native_status")
    if kind == "requester-sigkill":
        return status == -signal.SIGKILL
    if status != 0 or raw is None:
        return False
    message = "limits changed" if kind == "limit-drift" else "left its admitted cgroup"
    return (raw.get("success") is False and raw.get("cleanup_complete") is True
            and message in str(raw.get("observation_error")))


def _pause_until(deadline: int) -> None:
    while time.monotonic_ns() < deadline:
        remaining = max(0.0, (deadline - time.monotonic_ns()) / 1_000_000_000)
        time.sleep(min(0.01, remaining))


def _initial(work: Group) -> tuple[tuple[int, int], tuple[int, int]]:
    work_id = identity(work)
    parent = work.path.parent.stat()
    parent_id = (parent.st_dev, parent.st_ino)
    work_entry(work, parent_id, work_id)
    with os.scandir(work.fd) as entries:
        if any(entry.is_symlink() or entry.is_dir(follow_symlinks=False) for entry in entries):
            invalid("fault probes require an otherwise idle work branch")
    return parent_id, work_id


class _Case:
    def __init__(
        self, kind: str, work: Group, repo: Path, output: Path,
        environment: dict[str, str], deadline: int, record: dict[str, object],
        case: dict[str, object],
    ) -> None:
        self.kind = kind
        self.work = work
        self.repo = repo
        self.output = output
        self.environment = environment
        self.deadline = deadline
        self.record = record
        self.case = case
        self.worker: Worker | None = None
        self.subject: Subject | None = None
        self.parent_id: tuple[int, int] | None = None
        self.work_id: tuple[int, int] | None = None
        self.control_id: tuple[int, int] | None = None
        self.control_group: str | None = None

    def prepare(self) -> None:
        self.parent_id, self.work_id = _initial(self.work)
        self.control_id, self.control_group = controller_identity(self.work, self.parent_id)
        self.worker = start(
            self.work, self.repo, self.output / self.kind, self.environment,
            memory_mib=128, tasks=8, deadline=self.deadline, payload_deadline=self.deadline,
        )
        self.case["requester_pid"] = self.worker.process.pid
        self.case["worker_output"] = str(self.worker.root)
        self.subject = open_subject(self.work, self.worker, self.deadline)
        if self.subject.work_parent_id != self.parent_id or self.subject.work_id != self.work_id:
            invalid("fault probe work ownership changed during launch")
        if (self.subject.controller_id != self.control_id
                or self.subject.worker_cgroup != self.control_group):
            invalid("fault probe control ownership changed during launch")
        self.subject.verify_native()
        self.subject.verify_requester()
        self.case["native_start"] = self.subject.native
        self.case["work_identity"] = self.subject.work_id
        self.case["work_parent_identity"] = self.subject.work_parent_id
        self.case["work_limits"] = self.subject.work_limits
        self.case["control_identity"] = self.subject.controller_id
        self.case["control_membership"] = self.subject.worker_cgroup
        self.case["leaf_identity"] = self.subject.leaf_id
        self.case["leaf_before"] = self.subject.leaf.snapshot()
        _write(self.output, self.record)

    def inject(self) -> None:
        assert self.subject is not None
        if self.kind == "limit-drift":
            self.case["fault_spec"] = {"file": "pids.max", "before": 8, "after": 7}
        elif self.kind == "requester-sigkill":
            self.case["fault_spec"] = {"signal": "SIGKILL", "target": "owned-requester"}
        if self.kind == "membership-drift":
            create_target(self.subject)
            assert self.subject.target is not None
            self.case["fault_spec"] = {"target": "owned-sibling", "memory_mib": 128, "tasks": 8}
            self.case["target_identity"] = self.subject.target_id
            self.case["target_before"] = self.subject.target.snapshot()
            self.case["target_cleanup_role"] = "manual fixture removal after verdict"
        self.case["fault_dispatch_ns"] = time.monotonic_ns()
        _write(self.output, self.record)
        fired = _fault(self.subject, self.kind)
        self.case["fault_applied"] = True
        self.case["fault_attempted_ns"] = fired
        self.case["fault_applied_observed_ns"] = time.monotonic_ns()
        if self.kind == "membership-drift":
            self.case["target_membership_verified"] = True
        elif self.kind == "limit-drift":
            self.case["lower_limit_readback_verified"] = True

    def observe(self) -> None:
        subject = self.subject
        if subject is None or subject.fault_started_ns is None:
            self.case["unassisted"] = {"status": "fault-not-applied"}
            self.case["status"] = "nonpass"
            return
        observation = _observe(subject, subject.fault_started_ns)
        self.case["unassisted"] = observation
        try:
            raw = _kernel_record(subject.worker)
        except (OSError, ValueError, AssertionError) as error:
            self.case["raw_observation_error"] = f"{type(error).__name__}: {error}"
            raw = None
        self.case["raw_kernel_before_manual"] = raw
        try:
            self.case["raw_worker_before_manual"] = _worker_record(subject.worker)
        except (OSError, ValueError, AssertionError) as error:
            self.case["raw_worker_observation_error"] = f"{type(error).__name__}: {error}"
        expected = (
            self.case.get("fault_applied") is True
            and "raw_worker_observation_error" not in self.case
            and _expected(self.kind, observation, raw)
        )
        self.case["observed_expected_behavior"] = expected
        self.case["status"] = "observed-expected" if expected else "nonpass"

    def finish(self) -> bool:
        if (self.subject is not None and self.subject.fault_started_ns is not None
                and "unassisted" not in self.case):
            _pause_until(min(self.subject.fault_started_ns + WINDOW_NS,
                             self.subject.deadline - WINDOW_NS))
        verdict_ns = time.monotonic_ns()
        self.case["verdict_observed_ns"] = verdict_ns
        try:
            _write(self.output, self.record)
        except OSError as error:
            self.case["pre_cleanup_persistence_error"] = f"{type(error).__name__}: {error}"
            self.case["status"] = "nonpass"
        if self.subject is not None:
            return self._finish_bound(self.subject, verdict_ns)
        if self.worker is not None:
            return self._finish_unbound(self.worker)
        return True

    def _finish_unbound(self, worker: Worker) -> bool:
        if (self.parent_id is None or self.work_id is None or self.control_id is None
                or self.control_group is None):
            self.case["manual_cleanup_after_verdict"] = {"error": "ownership anchors unavailable"}
            return False
        self.case["manual_cleanup_after_verdict"] = stop_unbound(
            worker, self.work, self.parent_id, self.work_id,
            self.control_id, self.control_group, self.deadline,
        )
        return False

    def _finish_bound(self, subject: Subject, verdict_ns: int) -> bool:
        manual = manual_cleanup(subject, verdict_ns)
        close_errors = subject.close()
        self.case["manual_cleanup_after_verdict"] = manual
        self.case["descriptor_close_errors"] = close_errors
        if manual.get("errors") != [] or close_errors:
            self.case["status"] = "nonpass"
        if self.worker is not None:
            try:
                self.case["raw_kernel_after_manual"] = _kernel_record(self.worker)
                self.case["raw_worker_after_manual"] = _worker_record(self.worker)
            except (OSError, ValueError, AssertionError) as error:
                self.case["post_cleanup_record_error"] = f"{type(error).__name__}: {error}"
                self.case["status"] = "nonpass"
        return manual.get("errors") == [] and not close_errors

    def run(self) -> bool:
        self.case["status"] = "in-progress"
        _write(self.output, self.record)
        try:
            try:
                self.prepare()
                self.inject()
            except (OSError, ValueError, TypeError, RuntimeError, KeyError, AssertionError,
                    StopIteration) as error:
                self.case["error"] = f"{type(error).__name__}: {error}"
            self.observe()
        finally:
            cleaned = self.finish()
        return cleaned


def _run_cases(
    work: Group, repo: Path, output: Path, environment: dict[str, str], deadline: int,
    record: dict[str, object], cases: dict[str, dict[str, object]],
) -> None:
    for name, case in cases.items():
        record["active_case"] = name
        runner = _Case(name, work, repo, output, environment, deadline, record, case)
        if not runner.run():
            record["cleanup_incomplete"] = True
            break
        try:
            _initial(work)
        except (OSError, ValueError, RuntimeError, AssertionError) as error:
            record["cleanup_incomplete"] = True
            record["cleanup_error"] = f"{type(error).__name__}: {error}"
            break
        _write(output, record)
    else:
        record["status"] = (
            "observed-partial"
            if all(case.get("status") == "observed-expected" for case in cases.values())
            else "nonpass"
        )
        record.pop("active_case", None)
    if record["status"] == "in-progress":
        record["status"] = "nonpass"


def check(
    work: Group,
    repo: Path,
    scratch: Path,
    output: Path,
    environment: dict[str, str],
    *,
    ancestor_deadline_ns: int,
) -> dict[str, object]:
    """Record real bounded faults; manual cleanup never counts as automatic evidence."""
    started = time.monotonic_ns()
    output.mkdir(parents=True, exist_ok=False)
    deadline = min(ancestor_deadline_ns - WINDOW_NS, started + 60_000_000_000)
    cases: dict[str, dict[str, object]] = {
        name: {"status": "unrun"}
        for name in ("requester-sigkill", "limit-drift", "membership-drift")
    }
    record: dict[str, object] = {
        "status": "in-progress", "success": False, "cases": cases,
        "started_ns": started,
        "original_deadline_ns": ancestor_deadline_ns, "proof_deadline_ns": deadline,
        "maximum_unassisted_window_ns": WINDOW_NS, "scratch": str(scratch),
        "leaf_memory_mib": 128, "leaf_tasks": 8,
        "manual_cleanup_counts_as_automatic": False,
        "required_proofs_pending": list(PENDING),
    }
    _write(output, record)
    try:
        if deadline - time.monotonic_ns() < 15_000_000_000:
            invalid("insufficient original deadline for bounded fault probes")
        _initial(work)
        _run_cases(work, repo, output, environment, deadline, record, cases)
    except (OSError, ValueError, TypeError, RuntimeError, KeyError, AssertionError,
            StopIteration) as error:
        record["status"] = "nonpass"
        record["error"] = f"{type(error).__name__}: {error}"
    finally:
        record["finished_ns"] = time.monotonic_ns()
        if time.monotonic_ns() > deadline:
            record["status"] = "nonpass"
        try:
            _write(output, record)
        except OSError as error:
            record["status"] = "nonpass"
            record["persistence_error"] = f"{type(error).__name__}: {error}"
    return record
