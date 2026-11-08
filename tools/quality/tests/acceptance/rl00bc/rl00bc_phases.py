"""Route prepared, pinned-controller phases without changing their evidence scope."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import (
    rl00bc_adoption,
    rl00bc_candidates,
    rl00bc_compat,
    rl00bc_control,
    rl00bc_correctness,
    rl00bc_lifecycle,
    rl00bc_measure,
    rl00bc_methods,
)


@dataclass(frozen=True)
class _Phases:
    args: argparse.Namespace
    work: Group
    repo: Path
    environment: dict[str, str]

    def bound_environment(self) -> dict[str, str]:
        return {**self.environment, **rl00bc_control.context(self.args, self.repo, self.environment)}

    def prepare(self) -> dict[str, object]:
        return {"prepared": True}

    def correctness(self) -> dict[str, object]:
        return rl00bc_correctness.check(
            self.work, self.repo, self.args.scratch / "corpus", self.args.output / "correctness",
            self.args.profile, self.bound_environment(), ancestor_deadline_ns=self.args.deadline_ns,
        )

    def methods(self) -> dict[str, object]:
        return rl00bc_methods.check(
            self.work, self.repo, self.args.scratch / "corpus", self.args.output / "methods",
            self.args.profile, self.bound_environment(), ancestor_deadline_ns=self.args.deadline_ns,
        )

    def lifecycle(self) -> dict[str, object]:
        return rl00bc_lifecycle.check(
            self.work, self.repo, self.args.scratch / "lifecycle", self.args.output / "lifecycle",
            self.environment, ancestor_deadline_ns=self.args.deadline_ns,
        )

    def compatibility(self) -> dict[str, object]:
        return rl00bc_compat.reconcile(
            self.work, self.repo, self.args.scratch / "corpus", self.args.output / "compatibility",
            self.args.profile, self.environment, ancestor_deadline_ns=self.args.deadline_ns,
        )

    def candidates(self) -> dict[str, object]:
        return rl00bc_candidates.prove(
            self.work, self.repo, self.args.scratch / "candidates", self.args.output / "candidates",
            self.environment, ancestor_deadline_ns=self.args.deadline_ns,
        )

    def adoption(self) -> dict[str, object]:
        return rl00bc_adoption.adopt(
            self.work, self.repo, self.args.scratch / "adoption", self.args.output / "adoption",
            self.environment, ancestor_deadline_ns=self.args.deadline_ns,
        )

    def measure(self) -> dict[str, object]:
        return rl00bc_measure.measure(
            self.work, self.repo, self.args.scratch / "corpus", self.args.output / "measurement",
            self.args.profile, self.environment, samples=self.args.samples,
            criterion=self.args.criterion, approval=self.args.criterion_approval,
            ancestor_deadline_ns=self.args.deadline_ns,
        )


def run(args: argparse.Namespace, work: Group, repo: Path,
        environment: dict[str, str]) -> dict[str, object]:
    """Dispatch only after the caller has verified and prepared its native runtime."""
    phases = _Phases(args, work, repo, environment)
    return {
        "prepare": phases.prepare, "correctness": phases.correctness,
        "methods": phases.methods, "lifecycle": phases.lifecycle,
        "compatibility": phases.compatibility, "candidates": phases.candidates,
        "adoption": phases.adoption, "measure": phases.measure,
    }[args.phase]()
