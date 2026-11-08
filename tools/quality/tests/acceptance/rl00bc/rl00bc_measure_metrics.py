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


def memory(record: dict[str, object]) -> tuple[float, str]:
    raw = record.get("kernel")
    if not isinstance(raw, dict):
        invalid("kernel observation unavailable")
    kernel = cast(dict[str, object], raw)
    if kernel.get("memory_peak_bytes") is not None:
        return metric(record, "memory_peak_bytes"), "kernel-peak"
    return metric(record, "sampled_memory_peak_bytes"), "sampled-lower-bound"


def percentile(values: list[float], fraction: float) -> float:
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        invalid("percentile requires finite nonnegative observations")
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]
