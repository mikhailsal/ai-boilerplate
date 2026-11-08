"""Unrun, interleaved RL00c performance observations; criteria are proposals.

The baseline is canonical native execution in the mandatory finite suite leaf,
without instrumentation. The protected arm adds instrumented canonical work
and one fresh strict probe per discovered identity. Strict probes deliberately
disable coverage; only canonical execution supplies native coverage. No
shared-worker or narrow-selective performance comparison is measured here.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_trials

LIMIT = 1_048_576


def _write(path: Path, value: object) -> None:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > LIMIT:
        raise ValueError("measurement record exceeds finite size")
    path.write_bytes(data)


def _identities(profile: str, cases: object) -> list[str]:
    if not isinstance(cases, list) or not cases:
        raise ValueError("canonical producer returned no cases")
    key = "variant" if profile in ("python", "php") else "id"
    identities: list[str] = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get(key), str) or not case[key]:
            raise ValueError("native case lacks selector identity")
        identities.append(case[key])
    if len(set(identities)) != len(identities):
        raise ValueError("canonical selector identities are not unique")
    return identities


def _metric(record: dict[str, object], key: str) -> float:
    raw = record.get("kernel")
    if not isinstance(raw, dict):
        raise ValueError("kernel observation unavailable")
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"kernel metric {key} unavailable")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"invalid kernel metric {key}")
    return number


def _percentile(values: list[float], percentile: float) -> float:
    if not values or any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("percentile requires finite positive observations")
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


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
        raise ValueError("invalid profile or finite sample count")
    if criterion not in ("A", "B"):
        raise ValueError("unknown proposed criterion")
    output = output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    coverage = profile != "browser"
    summary: dict[str, object] = {
        "profile": profile,
        "requested_samples_per_size": samples,
        "criterion": criterion,
        "criterion_status": "proposed-not-owner-approved",
        "workers": 1,
        "canonical_coverage": coverage,
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
        "cells": {},
        "attempts": [],
        "status": "in-progress",
    }
    cells = summary["cells"]
    attempts = summary["attempts"]
    assert isinstance(cells, dict) and isinstance(attempts, list)
    _write(output / "measurement.json", summary)

    def arm(size: str, index: int, protected: bool) -> dict[str, object]:
        name = "protected" if protected else "native"
        directory = output / size / f"sample-{index:03d}" / name
        directory.mkdir(parents=True)
        attempt: dict[str, object] = {
            "size": size,
            "sample": index,
            "arm": name,
            "status": "in-progress",
            "trials": [],
        }
        attempts.append(attempt)
        _write(output / "measurement.json", summary)
        paths = attempt["trials"]
        assert isinstance(paths, list)
        started = time.monotonic_ns()
        controller_started = time.process_time()
        records: list[dict[str, object]] = []

        def run(selected: str | None, number: int, strict: bool) -> dict[str, object]:
            path = directory / f"trial-{number:03d}"
            paths.append(str(path))
            _write(output / "measurement.json", summary)
            record = rl00bc_trials.one(
                work,
                repo,
                scratch,
                path,
                profile,
                environment,
                selected=selected,
                size=size,
                mode="performance",
                target="",
                allocation_mib=1,
                shared_mib=64,
                workers=1,
                coverage=False if strict else coverage,
                instrument=protected,
                ancestor_deadline_ns=ancestor_deadline_ns,
            )
            records.append(record)
            if record.get("classification") != "observed-success":
                raise ValueError(
                    f"trial did not produce observed success: {record.get('classification')}"
                )
            return record

        canonical = run(None, 0, False)
        identities = _identities(profile, canonical.get("native_cases"))
        attempt["canonical_identities"] = identities
        if protected:
            for number, identity in enumerate(identities, 1):
                trial = run(identity, number, True)
                if _identities(profile, trial.get("native_cases")) != [identity]:
                    raise ValueError("strict result differs from canonical identity")
        wall_seconds = (time.monotonic_ns() - started) / 1_000_000_000
        controller_cpu_seconds = time.process_time() - controller_started
        native_cpu_seconds = sum(_metric(record, "cpu_seconds") for record in records)
        memory_peak = max(_metric(record, "memory_peak_bytes") for record in records)
        max_tasks = max(_metric(record, "max_tasks") for record in records)
        if wall_seconds <= 0 or not math.isfinite(wall_seconds):
            raise ValueError("invalid full-arm wall observation")
        attempt.update(
            {
                "status": "observed",
                "wall_seconds": wall_seconds,
                "native_cpu_seconds": native_cpu_seconds,
                "controller_cpu_seconds": controller_cpu_seconds,
                "total_cpu_seconds": native_cpu_seconds + controller_cpu_seconds,
                "max_leaf_memory_peak_bytes": memory_peak,
                "max_leaf_tasks": max_tasks,
                "strict_cases": len(identities) if protected else 0,
            }
        )
        _write(output / "measurement.json", summary)
        return attempt

    try:
        for size in ("small", "large"):
            native: list[float] = []
            protected: list[float] = []
            observations: dict[str, list[dict[str, object]]] = {"native": [], "protected": []}
            cell: dict[str, object] = {"status": "in-progress", "pairs": 0}
            cells[size] = cell
            for index in range(samples):
                results: dict[str, dict[str, object]] = {}
                for is_protected in (False, True) if index % 2 == 0 else (True, False):
                    result = arm(size, index, is_protected)
                    results[str(result["arm"])] = result
                if set(results["native"]["canonical_identities"]) != set(
                    results["protected"]["canonical_identities"]
                ):
                    raise ValueError("canonical identity set differs across paired arms")
                native.append(float(results["native"]["wall_seconds"]))
                protected.append(float(results["protected"]["wall_seconds"]))
                for arm_name in observations:
                    observations[arm_name].append(results[arm_name])
                cell["pairs"] = index + 1
                _write(output / "measurement.json", summary)
            native_p95 = _percentile(native, 0.95)
            protected_p95 = _percentile(protected, 0.95)
            multiplier, offset = (2.0, 2.0) if criterion == "A" else (1.5, 1.0)
            bound = multiplier * native_p95 + offset
            cell.update(
                {
                    "native_p50_seconds": _percentile(native, 0.50),
                    "native_p95_seconds": native_p95,
                    "protected_p50_seconds": _percentile(protected, 0.50),
                    "protected_p95_seconds": protected_p95,
                    "proposed_limit_seconds": bound,
                    "status": (
                        "insufficient-samples"
                        if samples < 20
                        else "proposed-criterion-pass"
                        if protected_p95 <= bound
                        else "no-go"
                    ),
                }
            )
            distributions: dict[str, dict[str, dict[str, float]]] = {}
            for arm_name, records in observations.items():
                distributions[arm_name] = {}
                for metric in (
                    "wall_seconds",
                    "total_cpu_seconds",
                    "max_leaf_memory_peak_bytes",
                    "max_leaf_tasks",
                ):
                    values = [float(record[metric]) for record in records]
                    distributions[arm_name][metric] = {
                        "p50": _percentile(values, 0.50),
                        "p95": _percentile(values, 0.95),
                    }
            cell["nearest_rank_distributions"] = distributions
            _write(output / "measurement.json", summary)
        summary["status"] = (
            "insufficient-samples"
            if samples < 20
            else "no-go"
            if any(cell["status"] == "no-go" for cell in cells.values())
            else "proposed-criteria-pass"
        )
    except Exception as error:
        if attempts and attempts[-1].get("status") == "in-progress":
            attempts[-1]["status"] = "nonpass"
        summary["status"] = "nonpass"
        summary["error"] = f"{type(error).__name__}: {error}"[:1024]
    _write(output / "measurement.json", summary)
    return summary
