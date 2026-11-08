"""Unrun, interleaved RL00c performance observations; criteria are proposals.

The baseline is canonical native execution in the mandatory finite suite leaf,
without instrumentation. The protected arm adds instrumented canonical work
and one fresh strict probe per discovered identity. Strict probes deliberately
disable coverage; only canonical execution supplies native coverage. No
shared-worker or narrow-selective performance comparison is measured here.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_corpus, rl00bc_measure_parity, rl00bc_trials
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_measure_metrics import (
    distributions,
    identities,
    leaf_maxima,
    metric,
    percentile,
    write,
)

SIZES = ("small", "large")
DISTRIBUTION_METRICS = (
    "wall_seconds",
    "payload_and_controller_cpu_seconds",
    "max_leaf_memory_peak_bytes",
    "max_leaf_tasks",
)


@dataclass
class _Measurement:
    work: Group
    repo: Path
    scratch: Path
    output: Path
    profile: str
    environment: dict[str, str]
    deadline: int
    samples: int
    criterion: str
    summary: dict[str, object]
    cells: dict[str, dict[str, object]]
    attempts: list[dict[str, object]]

    @property
    def coverage(self) -> bool:
        return self.profile != "browser"

    def persist(self) -> None:
        write(self.output / "measurement.json", self.summary)

    def pair(self, size: str, index: int) -> dict[str, dict[str, object]]:
        results: dict[str, dict[str, object]] = {}
        order = (False, True) if index % 2 == 0 else (True, False)
        for protected in order:
            result = _Arm(self, size, index, protected).run()
            results["protected" if protected else "native"] = result
        results["protected"]["paired_canonical_evidence"] = rl00bc_measure_parity.paired(
            results["native"], results["protected"]
        )
        return results

    def complete_cell(
        self,
        cell: dict[str, object],
        observations: dict[str, list[dict[str, object]]],
    ) -> None:
        native = [cast(float, item["wall_seconds"]) for item in observations["native"]]
        protected = [cast(float, item["wall_seconds"]) for item in observations["protected"]]
        if len(native) != 20 or len(protected) != 20 or self.samples != 20:
            invalid("timing criterion requires the exact preregistered twenty valid pairs")
        native_p95 = percentile(native, 0.95)
        protected_p95 = percentile(protected, 0.95)
        multiplier, offset = (2.0, 2.0) if self.criterion == "A" else (1.5, 1.0)
        bound = multiplier * native_p95 + offset
        cell.update(
            {
                "native_p50_seconds": percentile(native, 0.50),
                "native_p95_seconds": native_p95,
                "protected_p50_seconds": percentile(protected, 0.50),
                "protected_p95_seconds": protected_p95,
                "proposed_limit_seconds": bound,
                "status": (
                    "insufficient-samples"
                    if self.samples < 20
                    else "proposed-criterion-pass"
                    if protected_p95 <= bound
                    else "no-go"
                ),
            }
        )
        cell["nearest_rank_distributions"] = distributions(observations, DISTRIBUTION_METRICS)
        self.persist()

    def cell(self, size: str) -> bool:
        observations: dict[str, list[dict[str, object]]] = {"native": [], "protected": []}
        cell: dict[str, object] = {"status": "in-progress", "pairs": 0}
        self.cells[size] = cell
        for index in range(self.samples):
            results = self.pair(size, index)
            for name in observations:
                observations[name].append(results[name])
            cell["pairs"] = index + 1
            self.persist()
        self.complete_cell(cell, observations)
        if cell["status"] != "no-go":
            return False
        self.summary["stop_reason"] = "complete cell exceeded the proposed criterion"
        self.summary["decisive_cell"] = size
        for remaining in SIZES:
            if remaining not in self.cells:
                self.cells[remaining] = {"status": "unrun-after-no-go", "pairs": 0}
        return True

    def incomplete(self, error: Exception) -> None:
        if self.attempts and self.attempts[-1].get("status") == "in-progress":
            self.attempts[-1]["status"] = "nonpass"
        self.summary["status"] = "nonpass"
        self.summary["error"] = f"{type(error).__name__}: {error}"[:1024]
        for size in SIZES:
            cell = self.cells.setdefault(size, {"status": "unrun-after-incomplete", "pairs": 0})
            if cell["status"] == "in-progress":
                cell["status"] = "incomplete"

    def run(self) -> dict[str, object]:
        try:
            for size in SIZES:
                if self.cell(size):
                    break
            self.summary["status"] = (
                "insufficient-samples"
                if self.samples < 20
                else "no-go"
                if any(cell["status"] == "no-go" for cell in self.cells.values())
                else "timing-cells-pass-required-proofs-pending"
            )
        except (OSError, ValueError, TypeError, RuntimeError, KeyError, AssertionError) as error:
            self.incomplete(error)
        self.persist()
        return self.summary


@dataclass
class _Arm:
    measurement: _Measurement
    size: str
    index: int
    protected: bool
    directory: Path = field(init=False)
    attempt: dict[str, object] = field(init=False)
    paths: list[str] = field(default_factory=list[str])
    records: list[dict[str, object]] = field(default_factory=list[dict[str, object]])

    def trial(self, selected: str | None, number: int, *, strict: bool) -> dict[str, object]:
        context = self.measurement
        path = self.directory / f"trial-{number:03d}"
        self.paths.append(str(path))
        context.persist()
        record = rl00bc_trials.one(
            context.work,
            context.repo,
            context.scratch,
            path,
            context.profile,
            context.environment,
            selected=selected,
            size=self.size,
            mode="performance",
            target="",
            allocation_mib=1,
            shared_mib=64,
            workers=1,
            coverage=False if strict else context.coverage,
            instrument=self.protected,
            ancestor_deadline_ns=context.deadline,
        )
        self.records.append(record)
        if record.get("classification") != "observed-success":
            invalid(f"trial did not produce observed success: {record.get('classification')}")
        return record

    def finish(self, started: int, controller_started: float, case_count: int) -> None:
        wall = (time.monotonic_ns() - started) / 1_000_000_000
        controller_cpu = time.process_time() - controller_started
        native_cpu = sum(metric(record, "cpu_seconds") for record in self.records)
        if wall <= 0 or not math.isfinite(wall):
            invalid("invalid full-arm wall observation")
        self.attempt.update(
            {
                "status": "observed",
                "wall_seconds": wall,
                "native_cpu_seconds": native_cpu,
                "controller_cpu_seconds": controller_cpu,
                "payload_and_controller_cpu_seconds": native_cpu + controller_cpu,
                **leaf_maxima(self.records),
                "strict_cases": case_count if self.protected else 0,
            }
        )
        self.measurement.persist()

    def run(self) -> dict[str, object]:
        context = self.measurement
        name = "protected" if self.protected else "native"
        self.directory = context.output / self.size / f"sample-{self.index:03d}" / name
        self.directory.mkdir(parents=True)
        self.attempt = {
            "size": self.size,
            "sample": self.index,
            "arm": name,
            "status": "in-progress",
            "trials": self.paths,
        }
        context.attempts.append(self.attempt)
        context.persist()
        started, controller_started = time.monotonic_ns(), time.process_time()
        canonical = self.trial(None, 0, strict=False)
        rl00bc_corpus.verify(context.profile, self.size, canonical.get("native_cases"))
        discovered = identities(context.profile, canonical.get("native_cases"))
        self.attempt["canonical_identities"] = discovered
        self.attempt["canonical_evidence"] = rl00bc_measure_parity.canonical(
            context.profile, self.size, canonical
        )
        if self.protected:
            expected = {
                case.selector: case for case in rl00bc_corpus.expected(context.profile, self.size)
            }
            strict_evidence: list[dict[str, object]] = []
            self.attempt["strict_native_evidence"] = strict_evidence
            for number, identity in enumerate(discovered, 1):
                trial = self.trial(identity, number, strict=True)
                strict_evidence.append(
                    rl00bc_measure_parity.selected(expected[identity], canonical, trial)
                )
        self.finish(started, controller_started, len(discovered))
        return self.attempt


def _summary(
    profile: str,
    environment: dict[str, str],
    samples: int,
    criterion: str,
    cells: dict[str, dict[str, object]],
    attempts: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "profile": profile,
        "requested_samples_per_size": samples,
        "criterion": criterion,
        "criterion_status": "proposed-not-owner-approved",
        "workers": 1,
        "canonical_coverage": profile != "browser",
        "strict_coverage": False,
        "baseline": "canonical native under finite suite protection, no instrumentation",
        "protected": "instrumented canonical plus fresh strict probes for every discovered case",
        "independent_measurements": ["native canonical", "protected canonical plus strict all"],
        "not_measured": [
            "shared-worker instrumentation",
            "narrow selective checking",
            "adoption",
            "verdict usefulness",
            "actual candidate-bound selection and broad/full/first-adoption decision cost",
            "separate startup, collection and shared fixture costs",
            "guardian/provider CPU and total invocation memory/tasks",
        ],
        "metric_scope": {
            "wall": (
                "prepared arm including fixture materialization, runtime startup, parsing "
                "and controller; provider/bootstrap setup excluded"
            ),
            "cpu": "native payload leaves plus controller; guardian/provider excluded",
            "memory": "maximum individual leaf peak; not total invocation memory",
            "tasks": "maximum sampled leaf count, a lower bound",
        },
        "proposed_stop_rule": (
            "stop after a complete required ordinary timing cell exceeds the approved bound; "
            "owner workflow review required"
        ),
        "runtime_inputs": {
            key: value for key, value in environment.items() if key in rl00bc_trials.PATH_KEYS
        },
        "shared_mib": 64,
        "mode": "performance",
        "cells": cells,
        "attempts": attempts,
        "status": "in-progress",
    }


def measure(
    work: Group,
    repo: Path,
    scratch: Path,
    output: Path,
    profile: str,
    environment: dict[str, str],
    *,
    ancestor_deadline_ns: int,
    samples: int = 20,
    criterion: str = "A",
    approval: str = "",
) -> dict[str, object]:
    """Capture AB/BA pairs, stopping at the first incomplete or invalid attempt."""
    if profile not in rl00bc_trials.PROVIDERS or samples != 20:
        invalid("profile and exact preregistered twenty-pair sample count required")
    if criterion not in ("A", "B"):
        invalid("unknown proposed criterion")
    if not approval.strip() or len(approval) > 256 or "\0" in approval:
        invalid("measurement requires an explicit owner criterion approval reference")
    output = output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    cells: dict[str, dict[str, object]] = {}
    attempts: list[dict[str, object]] = []
    summary = _summary(profile, environment, samples, criterion, cells, attempts)
    summary["criterion_approval"] = approval
    summary["criterion_status"] = (
        "caller-asserted-owner-review; independent approval audit required"
    )
    run = _Measurement(
        work,
        repo,
        scratch,
        output,
        profile,
        environment,
        ancestor_deadline_ns,
        samples,
        criterion,
        summary,
        cells,
        attempts,
    )
    run.persist()
    return run.run()
