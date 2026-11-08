"""Bind timing samples to exact native identities, variants, outcomes and exits."""

from __future__ import annotations

from typing import cast

from tests.acceptance.rl00bc import rl00bc_corpus, rl00bc_dart_binding
from tests.acceptance.rl00bc.rl00bc_errors import invalid


def _exit(record: dict[str, object]) -> int:
    kernel = record.get("kernel")
    if not isinstance(kernel, dict):
        invalid("timing sample has no kernel observation")
    raw = cast(dict[str, object], kernel)
    status = raw.get("native_status")
    if type(status) is not int or status != 0 or raw.get("cleanup_complete") is not True:
        invalid("timing sample lacks native zero and complete cleanup")
    return status


def _row(row: dict[str, object], record: dict[str, object]) -> dict[str, object]:
    value = row.get("source")
    source = None
    if value is not None:
        source = rl00bc_dart_binding.relative_source(value, record.get("corpus_root"))
        if source is None:
            invalid("timing sample native source cannot be bound to its corpus")
    return {"id": row["id"], "variant": row.get("variant", "default"),
            "outcome": row.get("outcome"), "source": source,
            "source_state": "native-source-observed" if source is not None else "unavailable"}


def canonical(profile: str, size: str, record: dict[str, object]) -> dict[str, object]:
    """Retain producer rows without substituting selector strings for native IDs."""
    rows = rl00bc_corpus.verify(profile, size, record.get("native_cases"))
    normalized = [_row(row, record) for row in rows]
    normalized.sort(key=lambda row: (str(row["id"]), str(row["variant"])))
    return {"rows": normalized, "native_status": _exit(record),
            "source_scope": "compare actual producer sources where supplied; absence stays explicit"}


def selected(case: rl00bc_corpus.Case, baseline: dict[str, object],
             strict: dict[str, object]) -> dict[str, object]:
    """Reject a different native ID even when its parameter selector is identical."""
    rl00bc_corpus.verify_selected(case, strict.get("native_cases"))
    rows = cast(list[dict[str, object]], strict["native_cases"])
    value = baseline.get("native_cases")
    if not isinstance(value, list):
        invalid("timing baseline has no native rows")
    original = [cast(dict[str, object], row) for row in cast(list[object], value)
                if isinstance(row, dict)]
    matches = [row for row in original if row.get("id") == case.identity
               and row.get("variant", "default") == case.variant]
    if len(matches) != 1 or _row(matches[0], baseline) != _row(rows[0], strict):
        invalid("strict timing result differs from the actual canonical native row")
    return {"row": _row(rows[0], strict), "native_status": _exit(strict),
            "canonical_native_status": _exit(baseline)}


def _evidence(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        invalid("paired sample has malformed canonical evidence")
    data = cast(dict[str, object], value)
    rows, status = data.get("rows"), data.get("native_status")
    if not isinstance(rows, list) or not rows or type(status) is not int or status != 0:
        invalid("paired sample has no canonical rows or native zero")
    items = cast(list[object], rows)
    if not all(isinstance(item, dict) for item in items):
        invalid("paired sample has malformed native rows")
    return data


def paired(first: dict[str, object], second: dict[str, object]) -> dict[str, object]:
    """Compare corresponding canonical producer evidence across interleaved arms."""
    before = _evidence(first.get("canonical_evidence"))
    after = _evidence(second.get("canonical_evidence"))
    if before != after:
        invalid("paired canonical native IDs, variants, outcomes, sources or exits differ")
    return {"matched": True, "scope": "recorded native rows and exits; unavailable sources remain unproved"}
