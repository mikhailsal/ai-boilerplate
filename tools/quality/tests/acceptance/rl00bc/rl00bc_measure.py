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
from tests.acceptance.rl00bc import rl00bc_trials
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_measure_metrics import (
    identities,
    memory,
    metric,
    percentile,
    write,
)

SIZES = ("small", "large")
DISTRIBUTION_METRICS = (
    "wall_seconds",
    "total_cpu_seconds",
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
        native = cast(list[str], results["native"]["canonical_identities"])
        protected_ids = cast(list[str], results["protected"]["canonical_identities"])
        if set(native) != set(protected_ids):
            invalid("canonical identity set differs across paired arms")
        return results

    def complete_cell(
        self, cell: dict[str, object], observations: dict[str, list[dict[str, object]]],
    ) -> None:
        native = [cast(float, item["wall_seconds"]) for item in observations["native"]]
        protected = [cast(float, item["wall_seconds"]) for item in observations["protected"]]
        native_p95 = percentile(native, 0.95)
        protected_p95 = percentile(protected, 0.95)
        multiplier, offset = (2.0, 2.0) if self.criterion == "A" else (1.5, 1.0)
        bound = multiplier * native_p95 + offset
        cell.update({
            "native_p50_seconds": percentile(native, 0.50),
            "native_p95_seconds": native_p95,
            "protected_p50_seconds": percentile(protected, 0.50),
            "protected_p95_seconds": protected_p95,
            "proposed_limit_seconds": bound,
            "status": (
                "insufficient-samples" if self.samples < 20
                else "proposed-criterion-pass" if protected_p95 <= bound else "no-go"
            ),
        })
        cell["nearest_rank_distributions"] = _distributions(observations)
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

    def run(self) -> dict[str, object]:
        try:
            for size in SIZES:
                if self.cell(size):
                    break
            self.summary["status"] = (
                "insufficient-samples" if self.samples < 20
                else "no-go" if any(cell["status"] == "no-go" for cell in self.cells.values())
                else "proposed-criteria-pass"
            )
        except (OSError, ValueError, TypeError, RuntimeError, KeyError, AssertionError) as error:
            if self.attempts and self.attempts[-1].get("status") == "in-progress":
                self.attempts[-1]["status"] = "nonpass"
            self.summary["status"] = "nonpass"
            self.summary["error"] = f"{type(error).__name__}: {error}"[:1024]
        self.persist()
        return self.summary


def _distributions(
    observations: dict[str, list[dict[str, object]]],
) -> dict[str, dict[str, dict[str, float]]]:
    distributions: dict[str, dict[str, dict[str, float]]] = {}
    for name, records in observations.items():
        distributions[name] = {}
        for field_name in DISTRIBUTION_METRICS:
            values = [cast(float, record[field_name]) for record in records]
            distributions[name][field_name] = {
                "p50": percentile(values, 0.50), "p95": percentile(values, 0.95),
            }
    return distributions


@dataclass
class _Arm:
    measurement: _Measurement
    size: str
    index: int
    protected: bool
    directory: Path = field(init=False)
    attempt: dict[str, object] = field(init=False)
    paths: list[str] = field(default_factory=list)
    records: list[dict[str, object]] = field(default_factory=list)

    def trial(self, selected: str | None, number: int, *, strict: bool) -> dict[str, object]:
        context = self.measurement
        path = self.directory / f"trial-{number:03d}"
        self.paths.append(str(path))
        context.persist()
        record = rl00bc_trials.one(
            context.work, context.repo, context.scratch, path, context.profile, context.environment,
            selected=selected, size=self.size, mode="performance", target="", allocation_mib=1,
            shared_mib=64, workers=1, coverage=False if strict else context.coverage,
            instrument=self.protected, ancestor_deadline_ns=context.deadline,
        )
        self.records.append(record)
        if record.get("classification") != "observed-success":
            invalid(f"trial did not produce observed success: {record.get('classification')}")
        return record

    def finish(self, started: int, controller_started: float, case_count: int) -> None:
        wall = (time.monotonic_ns() - started) / 1_000_000_000
        controller_cpu = time.process_time() - controller_started
        native_cpu = sum(metric(record, "cpu_seconds") for record in self.records)
        observations = [memory(record) for record in self.records]
        peak = max(value for value, _ in observations)
        kind = (
            "kernel-peak" if all(source == "kernel-peak" for _, source in observations)
            else "sampled-lower-bound"
        )
        max_tasks = max(metric(record, "max_tasks") for record in self.records)
        if wall <= 0 or not math.isfinite(wall):
            invalid("invalid full-arm wall observation")
        self.attempt.update({
            "status": "observed", "wall_seconds": wall, "native_cpu_seconds": native_cpu,
            "controller_cpu_seconds": controller_cpu,
            "total_cpu_seconds": native_cpu + controller_cpu,
            "max_leaf_memory_peak_bytes": peak, "max_leaf_memory_peak_kind": kind,
            "max_leaf_tasks": max_tasks, "strict_cases": case_count if self.protected else 0,
        })
        self.measurement.persist()

    def run(self) -> dict[str, object]:
        context = self.measurement
        name = "protected" if self.protected else "native"
        self.directory = context.output / self.size / f"sample-{self.index:03d}" / name
        self.directory.mkdir(parents=True)
        self.attempt = {
            "size": self.size, "sample": self.index, "arm": name,
            "status": "in-progress", "trials": self.paths,
        }
        context.attempts.append(self.attempt)
        context.persist()
        started, controller_started = time.monotonic_ns(), time.process_time()
        canonical = self.trial(None, 0, strict=False)
        discovered = identities(context.profile, canonical.get("native_cases"))
        self.attempt["canonical_identities"] = discovered
        if self.protected:
            for number, identity in enumerate(discovered, 1):
                trial = self.trial(identity, number, strict=True)
                if identities(context.profile, trial.get("native_cases")) != [identity]:
                    invalid("strict result differs from canonical identity")
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
        ],
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
) -> dict[str, object]:
    """Capture AB/BA pairs, stopping at the first incomplete or invalid attempt."""
    if profile not in rl00bc_trials.PROVIDERS or not 1 <= samples <= 100:
        invalid("invalid profile or finite sample count")
    if criterion not in ("A", "B"):
        invalid("unknown proposed criterion")
    output = output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    cells: dict[str, dict[str, object]] = {}
    attempts: list[dict[str, object]] = []
    summary = _summary(profile, environment, samples, criterion, cells, attempts)
    run = _Measurement(
        work, repo, scratch, output, profile, environment, ancestor_deadline_ns,
        samples, criterion, summary, cells, attempts,
    )
    run.persist()
    return run.run()
