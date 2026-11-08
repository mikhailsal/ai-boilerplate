"""Reconcile Vitest selection with preregistered native identities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tests.acceptance.rl00bc import rl00bc_corpus
from tests.acceptance.rl00bc.rl00bc_errors import invalid


def selection(output: Path, profile: str, size: str, selected: str | None) -> None:
    """Bind a selector to the fixed corpus before the native command runs."""
    expected = rl00bc_corpus.expected(profile, size)
    identities = sorted(case.identity for case in expected)
    if selected is not None and selected not in {case.selector for case in expected}:
        invalid("selected identity is not in the preregistered corpus")
    data = {"profile": profile, "size": size, "selected": selected, "expected": identities}
    (output / "selection.json").write_text(
        json.dumps(data, sort_keys=True) + "\n", encoding="utf-8"
    )


def _saved_expected(value: object, expected: set[str]) -> None:
    if not isinstance(value, list) or cast(list[object], value) != sorted(expected):
        invalid("Vitest selection binding differs from the preregistered corpus")


def _binding(output: Path) -> tuple[str | None, set[str]]:
    raw: object = json.loads((output / "selection.json").read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        invalid("missing Vitest selection binding")
    data = cast(dict[str, object], raw)
    size = data.get("size")
    selected = data.get("selected")
    if data.get("profile") != "node" or not isinstance(size, str):
        invalid("invalid Vitest selection binding")
    if selected is not None and not isinstance(selected, str):
        invalid("invalid Vitest selected identity")
    expected = {case.identity for case in rl00bc_corpus.expected("node", size)}
    _saved_expected(data.get("expected"), expected)
    if selected is not None and selected not in expected:
        invalid("Vitest selected identity is not preregistered")
    return selected, expected


def _rows(cases: list[dict[str, object]], expected: set[str]) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for case in cases:
        identity, status = case.get("id"), case.get("outcome")
        if not isinstance(identity, str) or identity not in expected or identity in rows:
            invalid("unexpected or duplicate Vitest identity")
        if status not in ("passed", "failed", "skipped", "pending", "todo", "disabled"):
            invalid("unknown Vitest outcome")
        if case.get("variant", "default") != "default":
            invalid("unexpected Vitest variant")
        rows[identity] = case
    return rows


def reconcile(output: Path, cases: list[dict[str, object]]) -> list[dict[str, object]]:
    """Keep explicit filter skips as metadata and reject unexpected execution."""
    selected, expected = _binding(output)
    rows = _rows(cases, expected)
    if selected is None:
        if set(rows) != expected:
            invalid("canonical Vitest report differs from the preregistered corpus")
        return cases
    if selected not in rows:
        invalid("selected Vitest identity is missing")
    filtered: list[dict[str, object]] = []
    for identity, row in rows.items():
        if identity == selected:
            continue
        if row.get("outcome") != "skipped" or row.get("duration_ms") is not None:
            invalid(f"unselected Vitest case was not explicitly unexecuted: {identity}")
        if row.get("failure_messages") not in (None, []):
            invalid(f"unselected Vitest case has failure evidence: {identity}")
        filtered.append(
            {
                "id": identity,
                "source": row.get("source"),
                "outcome": "skipped",
                "duration_ms": row.get("duration_ms"),
                "failure_messages": row.get("failure_messages"),
            }
        )
    selected_row = dict(rows[selected])
    selected_row["filtered_out"] = filtered
    selected_row["selection_binding"] = str(output / "selection.json")
    return [selected_row]
