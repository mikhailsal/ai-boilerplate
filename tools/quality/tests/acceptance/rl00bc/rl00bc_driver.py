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
PHASES = ("prepare", "correctness", "compatibility", "candidates", "adoption", "measure")


def _phase(args: argparse.Namespace, work: Group, environment: dict[str, str]) -> dict[str, object]:
    # These modules require prepared core dependencies; system-Python startup
    # imports only stdlib-backed provider/kernel primitives before re-exec.
    from tests.acceptance.rl00bc import rl00bc_adoption, rl00bc_candidates, rl00bc_compat
    from tests.acceptance.rl00bc import rl00bc_correctness, rl00bc_measure

    options: dict[str, int] = {"ancestor_deadline_ns": args.deadline_ns}
    if args.phase == "prepare":
        return {"prepared": True}
    if args.phase == "correctness":
        return rl00bc_correctness.check(
            work, REPO, args.scratch / "corpus", args.output / "correctness", args.profile,
            {**environment, **rl00bc_control.context(args, REPO, environment)}, **options,
        )
    if args.phase == "compatibility":
        return rl00bc_compat.reconcile(
            work, REPO, args.scratch / "corpus", args.output / "compatibility", args.profile,
            environment, **options,
        )
    if args.phase == "candidates":
        return rl00bc_candidates.prove(
            work, REPO, args.scratch / "candidates", args.output / "candidates", environment, **options,
        )
    if args.phase == "adoption":
        return rl00bc_adoption.adopt(
            work, REPO, args.scratch / "adoption", args.output / "adoption", environment, **options,
        )
    return rl00bc_measure.measure(
        work, REPO, args.scratch / "corpus", args.output / "measurement", args.profile,
        environment, samples=args.samples, criterion=args.criterion, **options,
    )


def _adoption_passed(result: dict[str, object]) -> bool:
    phases = result.get("phases")
    if not isinstance(phases, list) or not phases:
        return False
    return all(_successful(item) for item in cast(list[object], phases))


def _successful(value: object) -> bool:
    return isinstance(value, dict) and cast(dict[str, object], value).get("success") is True


def comparison_passed(phase: str, result: dict[str, object]) -> bool:
    """Stop dependent jobs on failed comparisons without certifying integration."""
    return {
        "prepare": result.get("prepared") is True,
        "correctness": result.get("verdict") == "comparisons-passed-external-proofs-pending",
        "compatibility": result.get("verdict") == "pass",
        "candidates": result.get("success") is True,
        "measure": result.get("status") == "proposed-criteria-pass",
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
        save(args.output / "phase.json", {
            "phase": args.phase, "result": result, "collection_complete": True,
            "comparison_passed": accepted, "stage_acceptance": "separate-audit-required",
        })
        return 0 if accepted else 2
    finally:
        os.close(group.fd)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--profile", choices=("dart", "node", "browser", "php", "python"), default="python")
    parser.add_argument("--mode", choices=("host", "prepared"), default="host")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--criterion", choices=("A", "B"), default="A")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("--runtime-ready", action="store_true")
    parser.add_argument("--work-fd", type=int)
    parser.add_argument("--parent-fd", type=int)
    parser.add_argument("--work-name")
    parser.add_argument("--lifecycle-fd", type=int)
    parser.add_argument("--deadline-ns", type=int)
    result = parser.parse_args()
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
        REPO, args.output, args.scratch, args.phase, args.profile, args.mode, args.criterion, args.samples
    )
    return rl00bc_outside.run(request, HERE)


if __name__ == "__main__":
    raise SystemExit(main())
