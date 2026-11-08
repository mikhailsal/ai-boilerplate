"""Bounded research selection record; this is not a persisted impact map."""

from __future__ import annotations

import hashlib
import json
from typing import cast

from tests.acceptance.rl00bc.rl00bc_errors import invalid

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
        invalid("scope inputs must be finite JSON", cause=error)
    if len(data) > MAX_BYTES:
        invalid("scope exceeds 64 KiB")
    return data


def _context(context: dict[str, object]) -> None:
    for key in REQUIRED_CONTEXT:
        value = context.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 512:
            invalid(f"context requires nonempty bounded {key}")
    _encoded(context)


def _identities(discovered: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    if not discovered:
        invalid("no discovered cases")
    found: dict[str, dict[str, object]] = {}
    for case in discovered:
        identity = case.get("id")
        variant = case.get("variant")
        if not isinstance(identity, str) or not identity or len(identity) > 1024:
            invalid("invalid case identity")
        if not isinstance(variant, str) or not variant or len(variant) > 512:
            invalid("each identity needs an explicit variant")
        if identity in found:
            invalid("duplicate case identity")
        found[identity] = case
    _encoded(discovered)
    return found


def _unsafe_files(found: dict[str, dict[str, object]], changes: list[dict[str, str]]) -> str | None:
    if any(not isinstance(case.get("file"), str) or not case["file"] for case in found.values()):
        return "incomplete-native-file-mapping-full"
    if any(
        change.get("shared") != "false"
        or change.get("dynamic") != "false"
        or not change.get("path")
        for change in changes
    ):
        return "shared-dynamic-or-unknown-test-full"
    return None


def _file_selection(
    found: dict[str, dict[str, object]], changes: list[dict[str, str]]
) -> tuple[list[str], str]:
    all_ids = sorted(found)
    reason = _unsafe_files(found, changes)
    if reason is not None:
        return all_ids, reason
    paths = {change["path"] for change in changes}
    known = {cast(str, case["file"]) for case in found.values()}
    if not paths <= known:
        return all_ids, "unmapped-test-full"
    return sorted(
        identity for identity, case in found.items() if case["file"] in paths
    ), "complete-native-test-file-map"


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
    return _file_selection(found, changes)


def _validate_changes(changes: object) -> None:
    if not isinstance(changes, list):
        invalid("invalid changes")
    entries = cast(list[object], changes)
    for entry in entries:
        if not isinstance(entry, dict):
            invalid("invalid changes")
        pairs = cast(dict[object, object], entry)
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in pairs.items()):
            invalid("invalid changes")


def _validate_ids(value: object, *, message: str) -> list[str]:
    if not isinstance(value, list):
        invalid(message)
    items = cast(list[object], value)
    if any(not isinstance(item, str) for item in items):
        invalid(message)
    result = cast(list[str], items)
    if len(result) != len(set(result)):
        invalid(message)
    return result


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
        invalid("first_adoption must be boolean")
    _validate_changes(changes)
    selected, reason = _selection(context, found, changes, first_adoption)
    diagnostic = explicit_ids is not None
    if diagnostic:
        assert explicit_ids is not None
        _validate_ids(explicit_ids, message="explicit IDs must be unique discovered identities")
        if not explicit_ids or not set(explicit_ids) <= found.keys():
            invalid("explicit IDs must be unique discovered identities")
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
        invalid("stale context or discovered identities")
    if not isinstance(scope.get("changes"), list) or type(scope.get("first_adoption")) is not bool:
        invalid("invalid scope inputs")
    explicit = scope.get("explicit_ids")
    if explicit is not None:
        _validate_ids(explicit, message="invalid explicit identities")
    expected = build(
        context,
        discovered,
        cast(list[dict[str, str]], scope["changes"]),
        first_adoption=cast(bool, scope["first_adoption"]),
        explicit_ids=cast(list[str] | None, explicit),
    )
    if scope != expected:
        invalid("scope integrity or selection mismatch")
    _validate_ids(evidence_ids, message="invalid or duplicate strict evidence identities")
    if set(evidence_ids) != set(cast(list[str], scope["selected"])):
        invalid("missing or unexpected strict evidence identities")
