"""Bind native fixture events to identities actually observed in native reports."""

from __future__ import annotations

from typing import cast

CASE_PHASES = frozenset(
    f"{phase}-{boundary}"
    for phase in ("setup", "call", "teardown")
    for boundary in ("start", "end")
) | {"child-ready", "child-allocation-start", "child-allocation-end"}


def _emitters(events: list[dict[str, object]]) -> set[tuple[int, str]] | None:
    result: set[tuple[int, str]] = set()
    for event in events:
        pid = event.get("pid")
        if type(pid) is not int or pid <= 0:
            return None
        result.add((pid, str(event.get("worker", pid))))
    return result


def exclusivity(
    profile: str, identity: str, variant: str, events: list[dict[str, object]]
) -> dict[str, object]:
    """Assess every case event before allowing an incomplete-report identity bridge."""
    rows = [event for event in events if event.get("phase") in CASE_PHASES]
    unexpected = [event for event in rows if not _matches(event, profile, identity, variant)]
    emitters = _emitters(rows)
    no_competitor = not unexpected and emitters is not None and len(emitters) <= 1
    return {
        "case_event_count": len(rows),
        "unexpected_case_events": unexpected,
        "emitter_count": len(emitters) if emitters is not None else None,
        "no_competing_case": no_competitor,
        "single_case": bool(rows) and no_competitor,
    }


def report_has(run: dict[str, object], identity: str, variant: str, *, single: bool) -> bool:
    """Require an exact native identity/variant in the final or partial report."""
    if run.get("parse_error") is not None or run.get("selection_error") is not None:
        return False
    value = run.get("native_cases")
    if not isinstance(value, list):
        return False
    rows = cast(list[object], value)
    if single and len(rows) != 1:
        return False
    matches = 0
    for row in rows:
        if isinstance(row, dict):
            case = cast(dict[str, object], row)
            if case.get("id") == identity and case.get("variant", "default") == variant:
                matches += 1
    return matches == 1


def _python_id(value: object) -> str | None:
    if not isinstance(value, str) or "::" not in value:
        return None
    path, name = value.split("::", 1)
    if path != "test_subject.py":
        return None
    return f"test_subject::{name}"


def _matches(event: dict[str, object], profile: str, identity: str, variant: str) -> bool:
    if profile == "python":
        return _python_id(event.get("native_id")) == identity and event.get("variant") == variant
    if profile == "php":
        return event.get("variant") == variant and isinstance(event.get("native_id"), str)
    if profile == "node":
        return event.get("native_name") == identity
    if profile == "browser":
        return (
            event.get("native_name") == identity.removesuffix(f"[{variant}]")
            and event.get("native_project") == variant
        )
    return event.get("case") == identity


def _native_ids(events: list[dict[str, object]]) -> set[str]:
    result: set[str] = set()
    for event in events:
        value = event.get("native_id")
        if isinstance(value, str) and value:
            result.add(value)
    return result


def _php_bridge(
    canonical: list[dict[str, object]],
    strict: list[dict[str, object]],
    rows: list[dict[str, object]],
    variant: str,
) -> bool:
    canonical_ids = _native_ids(rows)
    strict_ids = _native_ids(strict)
    other_ids = _native_ids([event for event in canonical if event.get("variant") != variant])
    return (
        len(canonical_ids) == 1 and canonical_ids == strict_ids and not (canonical_ids & other_ids)
    )


def _bridge(
    profile: str,
    canonical: list[dict[str, object]],
    original: list[dict[str, object]],
    strict: list[dict[str, object]],
    variant: str,
    eligible: bool,
) -> tuple[bool, bool]:
    compatible = profile != "php" or _php_bridge(canonical, strict, original, variant)
    bridge = eligible and bool(original) and bool(strict) and profile != "dart" and compatible
    return bridge, compatible


def _binding_evidence(
    scope_valid: bool,
    exclusive: dict[str, object],
    report: bool,
    bridge: bool,
    canonical_report: bool,
) -> dict[str, object]:
    valid = scope_valid and exclusive["no_competing_case"] is True
    single = exclusive["single_case"] is True
    bridge = valid and single and bridge
    return {
        "canonical_report_identity": canonical_report,
        "strict_scope_valid": valid,
        "strict_report_identity": report,
        "canonical_event_bridge": bridge,
        "event_exclusivity": single,
        "event_exclusivity_evidence": exclusive,
        "strict_identity_bound": valid and single and (report or bridge),
    }


def select(
    profile: str,
    identity: str,
    variant: str,
    canonical: list[dict[str, object]],
    strict: list[dict[str, object]],
    canonical_report: bool,
    strict_report: bool,
    *,
    strict_scope_valid: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Use observed hooks as a bridge only where canonical mapping is unique."""
    canonical_rows = [event for event in canonical if _matches(event, profile, identity, variant)]
    strict_rows = [event for event in strict if _matches(event, profile, identity, variant)]
    exclusive = exclusivity(profile, identity, variant, strict)
    bridge, compatible = _bridge(
        profile,
        canonical,
        canonical_rows,
        strict_rows,
        variant,
        canonical_report,
    )
    return (
        canonical_rows,
        strict_rows,
        _binding_evidence(
            strict_scope_valid, exclusive, strict_report and compatible, bridge, canonical_report
        ),
    )
