"""Collect bounded RL00b/c evidence on CI; this is not a production test gate."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group, save
from tests.acceptance.rl00bc import rl00bc_control, rl00bc_outside
from tests.acceptance.rl00bc.rl00bc_errors import invalid

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
# Mirror rl00bc_adoption.FINAL_PHASE and UNRUN_PROOF; test_rl00bc_driver.py pins them together.
ADOPTION_FINAL_PHASE = "rollback-diff"
ADOPTION_UNRUN_PROOF = "missing_delegation"
PHASES = (
    "prepare",
    "correctness",
    "methods",
    "lifecycle",
    "nested",
    "faults",
    "selection-pressure",
    "compatibility",
    "candidates",
    "adoption",
    "measure",
    *rl00bc_outside.RACES,
)


def _phase(args: argparse.Namespace, work: Group, environment: dict[str, str]) -> dict[str, object]:
    # Core dependencies are available only after bounded preparation and re-exec.
    from tests.acceptance.rl00bc import rl00bc_phases

    return rl00bc_phases.run(args, work, REPO, environment)


def _unrun(value: object) -> bool:
    return isinstance(value, dict) and cast(dict[str, object], value).get("status") == "unrun"


def _successful(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    record = cast(dict[str, object], value)
    return record.get("success") is True and record.get("cleanup_complete") is True


def _adoption_passed(result: dict[str, object]) -> bool:
    """Accept only a finished export, onboarding, update and rollback chain.

    The producer runs its phases in sequence and stops at the first failure, so a
    successful final phase implies the earlier ones. Every recorded phase must still
    have succeeded; only the deliberately unrun delegation proof may be unrun, and a
    chain whose final phase is missing, unrun or failed never passes.
    """
    phases = result.get("phases")
    if not isinstance(phases, dict):
        return False
    recorded = cast(dict[str, object], phases)
    if not _successful(recorded.get(ADOPTION_FINAL_PHASE)):
        return False
    return all(
        _successful(item) or (name == ADOPTION_UNRUN_PROOF and _unrun(item))
        for name, item in recorded.items()
    )


def comparison_passed(phase: str, result: dict[str, object]) -> bool:
    """Stop dependent jobs on failed comparisons without certifying integration."""
    # These collections end at observed-partial while their other required proofs stay pending.
    partial = result.get("status") == "observed-partial"
    return {
        "prepare": result.get("prepared") is True,
        "correctness": result.get("verdict") == "comparisons-passed-external-proofs-pending",
        "compatibility": result.get("verdict") == "pass",
        "candidates": result.get("success") is True,
        "measure": result.get("status") == "timing-cells-pass-required-proofs-pending",
        "methods": result.get("status") == "observed-with-required-proofs-pending",
        "lifecycle": partial,
        "nested": partial,
        "faults": partial,
        "selection-pressure": result.get("success") is True,
        "adoption": _adoption_passed(result),
    }[phase]


def inside(args: argparse.Namespace) -> int:
    """Preserve verified handoffs and deadlines across core-runtime preparation."""
    group = rl00bc_control.work_group(args)
    try:
        if not args.runtime_ready:
            environment = rl00bc_control.prepare(group, args, REPO)
            rl00bc_control.reexec(group, args, REPO, environment)
        result = _phase(args, group, rl00bc_control.runtime(args))
        accepted = comparison_passed(args.phase, result)
        save(
            args.output / "phase.json",
            {
                "phase": args.phase,
                "result": result,
                "collection_complete": True,
                "comparison_passed": accepted,
                "stage_acceptance": "separate-audit-required",
            },
        )
        return 0 if accepted else 2
    finally:
        os.close(group.fd)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument(
        "--profile", choices=("dart", "node", "browser", "php", "python"), default="python"
    )
    parser.add_argument("--mode", choices=("host", "prepared"), default="host")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--criterion", choices=("A", "B"), default="A")
    parser.add_argument("--criterion-approval", default="")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("--runtime-ready", action="store_true")
    parser.add_argument("--work-fd", type=int)
    parser.add_argument("--parent-fd", type=int)
    parser.add_argument("--work-name")
    parser.add_argument("--lifecycle-fd", type=int)
    parser.add_argument("--deadline-ns", type=int)
    result = parser.parse_args()
    if result.inside and result.phase in rl00bc_outside.RACES:
        parser.error("guardian races require their dedicated external coordinator")
    if result.phase == "measure" and not result.criterion_approval.strip():
        parser.error("measurement requires an explicit criterion approval reference")
    if result.phase == "measure" and result.samples != 20:
        parser.error("measurement requires the preregistered twenty valid pairs per cell")
    if not 1 <= result.samples <= 100 or not result.scratch.is_absolute():
        parser.error("finite sample count and absolute scratch root required")
    result.output = result.output.absolute()
    return result


def _terminate(number: int, _frame: object) -> None:
    raise SystemExit(128 + number)


def main() -> int:
    if sys.flags.optimize:
        invalid("research safety assertions require unoptimized Python")
    args = _arguments()
    signal.signal(signal.SIGTERM, _terminate)
    if args.inside:
        return inside(args)
    request = rl00bc_outside.Request(
        REPO,
        args.output,
        args.scratch,
        args.phase,
        args.profile,
        args.mode,
        args.criterion,
        args.samples,
        args.criterion_approval,
    )
    return rl00bc_outside.run(request, HERE)


if __name__ == "__main__":
    raise SystemExit(main())
