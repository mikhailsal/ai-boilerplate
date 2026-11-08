"""Validate identities and calculate bounded RL00c measurement statistics."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import cast

from tests.acceptance.rl00bc.rl00bc_errors import invalid, wrong_type

LIMIT = 1_048_576


def write(path: Path, value: object) -> None:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > LIMIT:
        invalid("measurement record exceeds finite size")
    path.write_bytes(data)


def identities(profile: str, cases: object) -> list[str]:
    if not isinstance(cases, list) or not cases:
        invalid("canonical producer returned no cases")
    key = "variant" if profile in ("python", "php") else "id"
    result: list[str] = []
    for entry in cast(list[object], cases):
        if not isinstance(entry, dict):
            invalid("native case lacks selector identity")
        case = cast(dict[str, object], entry)
        identity = case.get(key)
        if not isinstance(identity, str) or not identity:
            invalid("native case lacks selector identity")
        result.append(identity)
    if len(set(result)) != len(result):
        invalid("canonical selector identities are not unique")
    return result


def metric(record: dict[str, object], key: str) -> float:
    raw = record.get("kernel")
    if not isinstance(raw, dict):
        wrong_type("kernel observation unavailable")
    value = cast(dict[str, object], raw).get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        wrong_type(f"kernel metric {key} unavailable")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        invalid(f"invalid kernel metric {key}")
    return number


def _sampled(record: dict[str, object]) -> None:
    raw = record.get("kernel")
    if not isinstance(raw, dict):
        invalid("kernel observation unavailable")
    count = cast(dict[str, object], raw).get("resource_sample_count")
    if type(count) is not int or count <= 0:
        invalid("sampled resource observation unavailable")


def memory(record: dict[str, object]) -> tuple[float, str]:
    raw = record.get("kernel")
    if not isinstance(raw, dict):
        invalid("kernel observation unavailable")
    kernel = cast(dict[str, object], raw)
    if kernel.get("memory_peak_bytes") is not None:
        return metric(record, "memory_peak_bytes"), "kernel-peak"
    _sampled(record)
    return metric(record, "sampled_memory_peak_bytes"), "sampled-lower-bound"


def tasks(record: dict[str, object]) -> tuple[float, str]:
    """Return the observed task high-water mark as a sampled lower bound."""
    _sampled(record)
    return metric(record, "max_tasks"), "sampled-lower-bound"


def percentile(values: list[float], fraction: float) -> float:
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        invalid("percentile requires finite nonnegative observations")
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def _distribution(records: list[dict[str, object]], field: str) -> dict[str, object]:
    kind_key = {"max_leaf_memory_peak_bytes": "max_leaf_memory_peak_kind",
                "max_leaf_tasks": "max_leaf_tasks_kind"}.get(field)
    grouped: dict[str, list[float]] = {}
    for record in records:
        kind = record.get(kind_key) if kind_key is not None else "measured"
        if kind not in ("measured", "kernel-peak", "sampled-lower-bound", "mixed-lower-bound"):
            invalid("distribution measurement kind is unavailable")
        value = record.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            invalid("distribution metric is unavailable")
        grouped.setdefault(cast(str, kind), []).append(float(value))
    return {"by_kind": {kind: {"samples": len(values), "p50": percentile(values, .50),
                              "p95": percentile(values, .95)}
                        for kind, values in grouped.items()}}


def distributions(observations: dict[str, list[dict[str, object]]],
                  fields: tuple[str, ...]) -> dict[str, object]:
    """Keep exact and sampled/lower-bound distributions distinct."""
    return {name: {field: _distribution(records, field) for field in fields}
            for name, records in observations.items()}
