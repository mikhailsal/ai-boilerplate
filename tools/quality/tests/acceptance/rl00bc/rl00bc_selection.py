"""Bounded research selection record; this is not a persisted impact map."""

from __future__ import annotations

import hashlib
import json
from typing import cast

MAX_BYTES = 65_536
REQUIRED_CONTEXT = ("candidate", "base", "tested_tree", "policy", "runtime", "source")
FULL_CHANGES = frozenset(
    {
        "source",
        "fixture",
        "data",
        "parameter",
        "dependency",
        "runtime",
        "config",
        "unknown",
        "volatile",
    }
)
MUTATION_ORACLE: tuple[dict[str, str], ...] = (
    {"change": "first_adoption", "expected": "full"},
    *({"change": kind, "expected": "full"} for kind in sorted(FULL_CHANGES)),
    {"change": "unmapped_test", "expected": "full"},
    {"change": "shared_or_dynamic_test", "expected": "full"},
    {"change": "mapped_native_test", "expected": "file_if_complete"},
    {"change": "explicit_id", "expected": "diagnostic_only"},
)


def _encoded(value: object) -> bytes:
    try:
        data = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("ascii")
    except (TypeError, ValueError) as error:
        raise ValueError("scope inputs must be finite JSON") from error
    if len(data) > MAX_BYTES:
        raise ValueError("scope exceeds 64 KiB")
    return data


def _context(context: dict[str, object]) -> None:
    for key in REQUIRED_CONTEXT:
        value = context.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 512:
            raise ValueError(f"context requires nonempty bounded {key}")
    _encoded(context)


def _identities(discovered: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    if not discovered:
        raise ValueError("no discovered cases")
    found: dict[str, dict[str, object]] = {}
    for case in discovered:
        identity = case.get("id")
        variant = case.get("variant")
        if not isinstance(identity, str) or not identity or len(identity) > 1024:
            raise ValueError("invalid case identity")
        if not isinstance(variant, str) or not variant or len(variant) > 512:
            raise ValueError("each identity needs an explicit variant")
        if identity in found:
            raise ValueError("duplicate case identity")
        found[identity] = case
    _encoded(discovered)
    return found


def _selection(
    context: dict[str, object],
    found: dict[str, dict[str, object]],
    changes: list[dict[str, str]],
    first: bool,
) -> tuple[list[str], str]:
    all_ids = sorted(found)
    if first:
        return all_ids, "first-adoption-full"
    if not changes:
        return all_ids, "unknown-influence-full"
    if any(
        change.get("kind") in FULL_CHANGES or change.get("kind") != "test" for change in changes
    ):
        return all_ids, "changed-or-unknown-influence-full"
    if context.get("native_file_mapping_complete") is not True:
        return all_ids, "incomplete-native-file-mapping-full"
    if any(not isinstance(case.get("file"), str) or not case["file"] for case in found.values()):
        return all_ids, "incomplete-native-file-mapping-full"
    if any(
        change.get("shared") != "false"
        or change.get("dynamic") != "false"
        or not change.get("path")
        for change in changes
    ):
        return all_ids, "shared-dynamic-or-unknown-test-full"
    paths = {change["path"] for change in changes}
    known = {cast(str, case["file"]) for case in found.values()}
    if not paths <= known:
        return all_ids, "unmapped-test-full"
    return sorted(
        identity for identity, case in found.items() if case["file"] in paths
    ), "complete-native-test-file-map"


def build(
    context: dict[str, object],
    discovered: list[dict[str, object]],
    changes: list[dict[str, str]],
    *,
    first_adoption: bool = False,
    explicit_ids: list[str] | None = None,
) -> dict[str, object]:
    """Bind all inputs to one record, conservatively selecting affected cases."""
    _context(context)
    found = _identities(discovered)
    if type(first_adoption) is not bool:
        raise ValueError("first_adoption must be boolean")
    if not isinstance(changes, list) or any(
        not isinstance(change, dict)
        or any(not isinstance(k, str) or not isinstance(v, str) for k, v in change.items())
        for change in changes
    ):
        raise ValueError("invalid changes")
    selected, reason = _selection(context, found, changes, first_adoption)
    diagnostic = explicit_ids is not None
    if diagnostic:
        assert explicit_ids is not None
        if (
            not explicit_ids
            or any(not isinstance(item, str) for item in explicit_ids)
            or len(set(explicit_ids)) != len(explicit_ids)
            or not set(explicit_ids) <= found.keys()
        ):
            raise ValueError("explicit IDs must be unique discovered identities")
        selected, reason = sorted(explicit_ids), "explicit-diagnostic-only"
    record: dict[str, object] = {
        "version": 1,
        "context": context,
        "discovered": discovered,
        "changes": changes,
        "first_adoption": first_adoption,
        "explicit_ids": explicit_ids,
        "selected": selected,
        "reason": reason,
        "automatic_selection": not diagnostic,
        "selection_soundness_proved": False,
        "canonical_success": None,
        "strict_evidence": "required-for-every-selected-case",
    }
    record["scope_sha256"] = hashlib.sha256(_encoded(record)).hexdigest()
    _encoded(record)
    # Return an independent snapshot so caller mutation cannot change bound inputs.
    return cast(dict[str, object], json.loads(_encoded(record)))


def verify(
    scope: dict[str, object],
    context: dict[str, object],
    discovered: list[dict[str, object]],
    evidence_ids: list[str],
) -> None:
    """Reject drift and missing evidence; caller must validate evidence freshness itself."""
    _context(context)
    _identities(discovered)
    _encoded(scope)
    if scope.get("context") != context or scope.get("discovered") != discovered:
        raise ValueError("stale context or discovered identities")
    if not isinstance(scope.get("changes"), list) or type(scope.get("first_adoption")) is not bool:
        raise ValueError("invalid scope inputs")
    explicit = scope.get("explicit_ids")
    if explicit is not None and (
        not isinstance(explicit, list) or any(not isinstance(item, str) for item in explicit)
    ):
        raise ValueError("invalid explicit identities")
    expected = build(
        context,
        discovered,
        cast(list[dict[str, str]], scope["changes"]),
        first_adoption=cast(bool, scope["first_adoption"]),
        explicit_ids=cast(list[str] | None, explicit),
    )
    if scope != expected:
        raise ValueError("scope integrity or selection mismatch")
    if (
        not isinstance(evidence_ids, list)
        or any(not isinstance(item, str) for item in evidence_ids)
        or len(evidence_ids) != len(set(evidence_ids))
    ):
        raise ValueError("invalid or duplicate strict evidence identities")
    if set(evidence_ids) != set(cast(list[str], scope["selected"])):
        raise ValueError("missing or unexpected strict evidence identities")
