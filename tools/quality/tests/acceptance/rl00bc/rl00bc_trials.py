"""Run one bounded native trial and preserve its evidence."""

from __future__ import annotations

import hashlib
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_kernel, rl00bc_native_results
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid
from tests.acceptance.rl00bc.rl00bc_trial_support import PATH_KEYS as PATH_KEYS
from tests.acceptance.rl00bc.rl00bc_trial_support import (
    PROVIDERS,
    RESERVE_NS,
    STRICT,
    environment_for,
    provider_commands,
    save_record,
)


@dataclass
class _Trial:
    work: Group
    repo: Path
    scratch: Path
    output: Path
    profile: str
    environment: dict[str, str]
    selected: str | None
    size: str
    mode: str
    target: str
    allocation_mib: int
    shared_mib: int
    workers: int
    coverage: bool
    instrument: bool
    justification: str | None
    ancestor_deadline_ns: int
    start_ns: int
    memory_mib: int = field(init=False)
    tasks: int = field(init=False)
    seconds: float = field(init=False)
    budget_class: str = field(init=False)
    deadline_ns: int = field(init=False)
    root: Path = field(init=False)
    env: dict[str, str] = field(init=False)
    plan_path: Path = field(init=False)
    plan_hash: str = field(init=False)
    preparation_seconds: float = field(init=False)

    def validate(self) -> None:
        if self.profile not in PROVIDERS or self.workers not in (1, 2):
            invalid("unsupported profile or workers")
        if self.selected is not None and (
            not self.selected or len(self.selected) > 256 or "\0" in self.selected
        ):
            invalid("invalid selected identity")
        self.memory_mib, self.tasks, self.seconds = (
            (3072, 256, 90.0) if self.selected is None else STRICT[self.profile]
        )
        self.budget_class = "canonical" if self.selected is None else "ordinary"
        self.allow_justified()
        self.deadline_ns = min(
            self.start_ns + int(self.seconds * 1_000_000_000),
            self.ancestor_deadline_ns - RESERVE_NS,
        )

    def allow_justified(self) -> None:
        if self.justification is None:
            return
        if (
            self.justification != "preregistered justified workload"
            or self.selected is None
            or self.mode != "correctness"
            or self.target != "justified"
            or self.memory_mib + 512 > 3072
        ):
            invalid("justified allowance is restricted to the preregistered selected workload")
        self.memory_mib += 512
        self.budget_class = "preregistered-justified"

    def prepare(self) -> None:
        self.repo, self.scratch, self.output = (
            self.repo.absolute(),
            self.scratch.absolute(),
            self.output.absolute(),
        )
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.output.mkdir(parents=True, exist_ok=False)
        self.root = self.scratch / f"rl00bc-{uuid.uuid4().hex}"
        self.env = environment_for(
            self.environment,
            self.root,
            self.output,
            size=self.size,
            mode=self.mode,
            target=self.target,
            allocation_mib=self.allocation_mib,
            shared_mib=self.shared_mib,
            instrument=self.instrument,
            coverage=self.coverage,
        )
        argv = provider_commands(
            PROVIDERS[self.profile],
            self.root,
            self.repo,
            self.output / "native",
            self.profile,
            self.selected,
            self.workers,
            self.coverage,
            self.env,
        )
        self.write_plan(argv)

    def write_plan(self, argv: list[str]) -> None:
        commands = [argv]
        if self.profile == "browser":
            if self.coverage:
                invalid("browser profile has no native unit coverage")
            commands.insert(
                0,
                [
                    self.env["RL00_NODE"],
                    str(Path(self.env["RL00_NODE_MODULES"]) / "vite/bin/vite.js"),
                    "build",
                    str(self.root),
                ],
            )
        if self.deadline_ns <= time.monotonic_ns():
            expired("trial deadline exhausted during preparation")
        plan = {
            "cwd": str(self.root),
            "commands": commands,
            "events": str(self.output / "events"),
            "deadline_ns": self.deadline_ns,
        }
        self.plan_path = self.output / "native-plan.json"
        self.plan_hash = hashlib.sha256(save_record(self.plan_path, plan)).hexdigest()
        self.preparation_seconds = (time.monotonic_ns() - self.start_ns) / 1_000_000_000

    def execute(self) -> dict[str, object]:
        wrapper = Path(__file__).with_name("rl00bc_native.py").absolute()
        return rl00bc_kernel.execute(
            self.work,
            [sys.executable, str(wrapper), str(self.plan_path)],
            self.root,
            self.env,
            self.output / "kernel",
            memory_mib=self.memory_mib,
            tasks=self.tasks,
            native_seconds=self.seconds,
            ancestor_deadline_ns=self.ancestor_deadline_ns,
            payload_deadline_ns=self.deadline_ns,
        )

    def record(self, raw: dict[str, object]) -> dict[str, object]:
        native = rl00bc_native_results.read(
            self.profile, self.root, self.output / "native", self.selected, raw
        )
        result: dict[str, object] = {
            "profile": self.profile,
            "selected": self.selected,
            "scope": "canonical-suite" if self.selected is None else "selected-case",
            "measurement_kind": "kernel-charged-leaf",
            **native,
            "strict_verification": "not-applicable"
            if self.selected is None
            else "experimental-evidence-only",
            "kernel": raw,
            "native_plan_sha256": self.plan_hash,
            "native_plan": str(self.plan_path),
            "preparation_seconds": self.preparation_seconds,
            "kernel_evidence": str(self.output / "kernel/result.json"),
            "events": str(self.output / "events"),
            "corpus_root": str(self.root),
            "memory_limit_mib": self.memory_mib,
            "task_limit": self.tasks,
            "native_deadline_ns": self.deadline_ns,
            "ancestor_deadline_ns": self.ancestor_deadline_ns,
            "size": self.size,
            "mode": self.mode,
            "target": self.target,
            "workers": self.workers,
            "allocation_mib": self.allocation_mib,
            "shared_mib": self.shared_mib,
            "coverage": self.coverage,
            "budget_class": self.budget_class,
            "justification": self.justification,
        }
        save_record(self.output / "trial.json", result)
        return result


def one(
    work: Group,
    repo: Path,
    scratch: Path,
    output: Path,
    profile: str,
    environment: dict[str, str],
    *,
    selected: str | None = None,
    size: str = "small",
    mode: str = "performance",
    target: str = "",
    allocation_mib: int = 1,
    shared_mib: int = 64,
    workers: int = 1,
    coverage: bool = True,
    instrument: bool = True,
    justification: str | None = None,
    ancestor_deadline_ns: int,
) -> dict[str, object]:
    """Run a fresh native subject under one leaf and persist separate evidence."""
    start_ns = time.monotonic_ns()
    trial = _Trial(
        work,
        repo,
        scratch,
        output,
        profile,
        environment,
        selected,
        size,
        mode,
        target,
        allocation_mib,
        shared_mib,
        workers,
        coverage,
        instrument,
        justification,
        ancestor_deadline_ns,
        start_ns,
    )
    trial.validate()
    trial.prepare()
    return trial.record(trial.execute())
