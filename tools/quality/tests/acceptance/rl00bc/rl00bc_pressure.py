"""Bounded real-candidate selection and native input-pressure experiment."""

from __future__ import annotations

import signal
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid
from tests.acceptance.rl00bc.rl00bc_pressure_worker import PressureExperiment, save_record

from quality.gitio.errors import GitioError
from quality.process import ProcessError


def _alarm(_number: int, _frame: object) -> None:
    expired("candidate pressure controller deadline expired")


@contextmanager
def _watchdog(deadline: int) -> Generator[None]:
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    if old_timer != (0.0, 0.0):
        invalid("pressure experiment cannot replace an existing controller timer")
    remaining = (deadline - time.monotonic_ns()) / 1_000_000_000
    if remaining <= 0:
        expired("candidate pressure deadline is already exhausted")
    old_handler = signal.signal(signal.SIGALRM, _alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL, remaining)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def _finish(result: dict[str, object], start: int, output: Path) -> dict[str, object]:
    elapsed = (time.monotonic_ns() - start) / 1_000_000_000
    result["elapsed_seconds"] = elapsed
    if elapsed > 60:
        result.update({"success": False, "classification": "deadline-nonpass"})
    save_record(output / "pressure.json", result)
    return result


def check(
    work: Group,
    repo: Path,
    scratch: Path,
    output: Path,
    environment: dict[str, str],
    *,
    ancestor_deadline_ns: int,
) -> dict[str, object]:
    """Compare a real changed candidate under canonical and strict finite leaves."""
    start = time.monotonic_ns()
    deadline = min(start + 55_000_000_000, ancestor_deadline_ns - 3_000_000_000)
    repo, scratch, output = repo.absolute(), scratch.absolute(), output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    scratch.mkdir(parents=True, exist_ok=False)
    result: dict[str, object] = {
        "success": False,
        "classification": "unproved",
        "start_ns": start,
        "deadline_ns": deadline,
        "ancestor_deadline_ns": ancestor_deadline_ns,
        "claim_limit": (
            "Finite Python fixture, actual Git candidate and native tests only; "
            "no general influence soundness or product hook/export integration."
        ),
    }
    runner: PressureExperiment | None = None
    try:
        python = Path(environment.get("RL00_PYTHON", ""))
        if not python.is_absolute() or not python.is_file():
            invalid("pressure experiment needs the pinned absolute Python interpreter")
        with _watchdog(deadline):
            runner = PressureExperiment(work, repo, scratch, output, python, deadline)
            runner.initialize()
            target, original = runner.baseline()
            expanded = runner.narrow(target)
            runner.mutated(target, original, expanded)
            runner.guard()
            result.update(
                {
                    "success": True,
                    "classification": "observed-fixture-comparison",
                    "evidence": runner.evidence,
                }
            )
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        GitioError,
        ProcessError,
        subprocess.SubprocessError,
    ) as error:
        result["error"] = f"{type(error).__name__}: {error}"[:1024]
        if runner is not None:
            result["evidence"] = runner.evidence
    return _finish(result, start, output)
