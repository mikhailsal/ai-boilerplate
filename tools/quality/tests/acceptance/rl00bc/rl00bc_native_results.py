"""Read native trial evidence and classify it without obscuring kernel causes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from tests.acceptance.rl00bc import rl00bc_dart
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_trial_support import PROVIDERS


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        invalid("partial native evidence has no case list")
    items = cast(list[object], value)
    if not all(isinstance(item, dict) for item in items):
        invalid("partial native evidence contains an invalid case")
    return cast(list[dict[str, object]], items)


def _selection_problem(
    selected: str | None, cases: list[dict[str, object]], partial: dict[str, object] | None
) -> str | None:
    if selected is None:
        return None
    if partial is not None and (partial.get("focused") is True or partial.get("truncated_tail") is True):
        return "partial native stream leaves selection trust or exclusivity unproved"
    matches = [case for case in cases if selected in (case.get("id"), case.get("variant"))]
    if len(cases) != 1 or len(matches) != 1:
        return "native selected identity missing, unexpected or visibility-ambiguous"
    return None


def _classification(
    kernel: dict[str, object], cases: list[dict[str, object]], parse_error: str | None
) -> str:
    violation = kernel.get("resource_violation")
    if violation in ("own-memory", "own-tasks"):
        return "own-boundary-resource-violation"
    if violation == "ancestor-resource":
        return "ancestor-resource-violation-unknown-case"
    if violation == "timeout":
        return "deadline-exceeded"
    if violation is not None:
        return "unclassified-resource-nonpass"
    if not kernel.get("success") or not kernel.get("cleanup_complete"):
        return "native-or-environment-nonpass"
    if parse_error is not None:
        return "invalid-native-evidence"
    if any(case.get("outcome") not in ("passed", "pass", "success", "expected") for case in cases):
        return "native-nonpass"
    return "observed-success"


def read(
    profile: str, root: Path, output: Path, selected: str | None, kernel: dict[str, object]
) -> dict[str, object]:
    """Read a native report and preserve partial evidence and raw-cause classification."""
    partial: dict[str, object] | None = None
    cases: list[dict[str, object]] = []
    parse_error: str | None = None
    selection_error: str | None = None
    try:
        if (profile == "dart" and kernel.get("success") is False
            and kernel.get("resource_violation") in
            ("own-memory", "own-tasks", "ancestor-resource", "timeout")):
            partial = rl00bc_dart.partial_results(root, output, profile=profile, kernel=kernel)
            cases = _rows(partial.get("native_cases"))
        else:
            cases = PROVIDERS[profile].results(root, output, profile=profile)
        selection_error = _selection_problem(selected, cases, partial)
        parse_error = selection_error
    except Exception as error:
        logging.exception("Native result parsing failed")
        parse_error = f"{type(error).__name__}: {error}"[:1024]
    return {
        "native_cases": cases, "partial_native_evidence": partial,
        "parse_error": parse_error, "selection_error": selection_error,
        "classification": _classification(kernel, cases, parse_error),
    }
