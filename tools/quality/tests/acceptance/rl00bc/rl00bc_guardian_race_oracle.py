"""Validate retained observations from an isolated guardian-race service."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import load
from tests.acceptance.rl00bc.rl00bc_errors import invalid


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        invalid("missing race evidence object")
    return cast(dict[str, object], value)


def _timestamp(value: object) -> int:
    if type(value) is not int or value <= 0:
        invalid("missing race timestamp")
    return value


def _launch(guardian: dict[str, object], closing: dict[str, object], output: Path) -> None:
    held = _object(guardian.get("race_handshake_held"))
    attempt = _object(guardian.get("race_closing_lock_attempt"))
    marker = _object(guardian.get("race_native_marker"))
    release = load(output / "race-release.json")
    if attempt.get("state") != "blocked" or held.get("pid") != marker.get("pid"):
        invalid("guardian did not block behind the native launcher")
    if held.get("lifecycle_inode") != guardian.get("lifecycle_inode"):
        invalid("race lifecycle identity differs")
    if not (
        _timestamp(held.get("held_ns"))
        <= _timestamp(attempt.get("observed_ns"))
        <= _timestamp(release.get("released_ns"))
        <= _timestamp(closing.get("closing_ns"))
    ):
        invalid("launch-first observations are out of order")
    if not isinstance(marker.get("leaf_inode"), int) or not marker.get("leaf_path"):
        invalid("native marker lacks owned leaf identity")


def _closing(guardian: dict[str, object], closing: dict[str, object], output: Path) -> None:
    ready = load(output / "race-controller-ready.json")
    release = load(output / "race-release.json")
    result = _object(guardian.get("race_controller_result"))
    native = _object(result.get("result"))
    if not (
        _timestamp(ready.get("ready_ns"))
        <= _timestamp(closing.get("closing_ns"))
        <= _timestamp(release.get("released_ns"))
        <= _timestamp(result.get("observed_ns"))
    ):
        invalid("closing-first observations are out of order")
    if result.get("work_inode") != ready.get("work_inode"):
        invalid("closing-first work identity changed")
    if result.get("children_before") != [] or result.get("children_after") != []:
        invalid("closing-first attempt created or changed a leaf")
    if result.get("native_marker_exists") is not False or (output / "race-marker.json").exists():
        invalid("closing-first attempt executed the native payload")
    if native.get("success") is not False or "session closing" not in str(
        native.get("observation_error")
    ):
        invalid("closing-first attempt did not retain the expected native nonpass")


def _guardian(guardian: dict[str, object], closing: dict[str, object]) -> None:
    if closing.get("lifecycle_inode") != guardian.get("lifecycle_inode"):
        invalid("closing marker lifecycle identity differs")
    if guardian.get("error") is not None or guardian.get("cleanup_errors") != []:
        invalid("guardian race reported an execution or cleanup error")
    if guardian.get("closing_published") is not True or guardian.get("stop_reason") != "race-probe":
        invalid("guardian did not publish closing for the race")
    status = guardian.get("controller_native_status")
    if type(status) is not int or status == 0:
        invalid("controller non-success exit was not reaped")
    deadline = _timestamp(guardian.get("cleanup_deadline_ns"))
    if any(
        _timestamp(guardian.get(key)) > deadline
        for key in ("work_absent_observed_ns", "control_absent_observed_ns", "finished_ns")
    ):
        invalid("guardian cleanup exceeded its fixed deadline")


def validate(race: str, guardian: dict[str, object], output: Path) -> dict[str, object]:
    """Assess expected race observations without changing the raw native outcome."""
    closing = load(output / "closing.json")
    _guardian(guardian, closing)
    if race == "launch-first":
        _launch(guardian, closing, output)
    elif race == "closing-first":
        _closing(guardian, closing, output)
    else:
        invalid("unknown guardian race")
    return {
        "race": race,
        "oracle": "observed",
        "guardian_success": guardian.get("success"),
        "controller_native_status": guardian.get("controller_native_status"),
        "pending": ["abrupt guardian death recovery", "abrupt controller death recovery"],
    }
