"""Compare emitted fixture phases without inferring case attribution from a kill."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import cast

from tests.acceptance.rl00bc import (
    rl00bc_dart_binding,
    rl00bc_event_binding,
    rl00bc_phase_window,
    rl00bc_resource_oracle,
    rl00bc_shared_oracle,
)

_PHASE = {"setup": "setup", "teardown": "teardown", "retained": "retained"}
_RETAINED = {
    "python": ("session-setup-start", "session-setup"),
    "php": ("class-setup-start", "class-setup-end"),
    "node": ("retained-allocation-start", "retained-allocation-end"),
    "browser": ("retained-allocation-start", "retained-allocation-end"),
    "dart": ("retained-allocation-start", "retained-allocation-end"),
}


def _events(run: dict[str, object]) -> tuple[list[dict[str, object]], list[str]]:
    directory = run.get("events")
    if not isinstance(directory, str) or not Path(directory).is_dir():
        return [], ["event directory unavailable"]
    events: list[dict[str, object]] = []
    gaps: list[str] = []
    for index, path in enumerate(Path(directory).glob("*.json")):
        if index >= 512:
            gaps.append("event directory exceeds its finite entry bound")
            break
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > 16_384:
                gaps.append(f"unsafe or oversized event: {path.name}")
                continue
            value: object = json.loads(path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            gaps.append(f"unreadable event: {path.name}")
            continue
        if isinstance(value, dict):
            events.append(cast(dict[str, object], value))
        else:
            gaps.append(f"invalid event: {path.name}")
    return events, gaps


def _case_name(profile: str, identity: str, variant: str) -> str:
    if profile in ("python", "php"):
        return variant
    if profile == "dart":
        return identity
    if profile == "browser":
        return identity.removeprefix("parameter:").rsplit("[", 1)[0]
    return identity


def _phases(
    events: list[dict[str, object]], profile: str, identity: str, variant: str, *, retained: bool
) -> set[str]:
    name = "retained" if retained else _case_name(profile, identity, variant)
    phases: set[str] = set()
    for event in events:
        label = event.get("label", event.get("case"))
        if label not in (name, f"parameter:{name}"):
            continue
        if profile == "browser" and not retained and event.get("variant") != variant:
            continue
        phase = event.get("phase")
        if isinstance(phase, str):
            phases.add(phase)
    return phases


def _phase_evidence(
    profile: str, target: str, canonical: set[str], strict: set[str], gaps: list[str]
) -> dict[str, object]:
    phase = _PHASE.get(target, "call")
    if phase == "retained":
        start, end = _RETAINED[profile]
        canonical_complete = {start, end} <= canonical
        entered = start in strict
        if profile in ("node", "browser", "dart"):
            gaps.append("retained shared event cannot be bound to an individual native case")
    else:
        required = {
            f"{part}-{boundary}"
            for part in ("setup", "call", "teardown")
            for boundary in ("start", "end")
        }
        canonical_complete = required <= canonical
        entered = f"{phase}-start" in strict
    if not canonical_complete:
        gaps.append("canonical phase completion not established")
    if not entered:
        gaps.append(f"strict {phase} entry not observed")
    return {
        "expected_phase": phase,
        "canonical_complete": canonical_complete,
        "strict_phase_entered": entered,
        "canonical_phases": sorted(canonical),
        "strict_phases": sorted(strict),
    }


def _retained_case_phases(phases: set[str], gaps: list[str]) -> dict[str, object]:
    required = {
        f"{part}-{boundary}"
        for part in ("setup", "call", "teardown")
        for boundary in ("start", "end")
    }
    complete = required <= phases
    if not complete:
        gaps.append("canonical retained case phases are incomplete")
    return {"phases": sorted(phases), "complete": complete}


def _entry(profile: str, target: str, events: list[dict[str, object]]) -> dict[str, object] | None:
    phase = rl00bc_phase_window.names(profile, target)[0]
    matches = [event for event in events if event.get("phase") == phase]
    return matches[0] if len(matches) == 1 else None


def _canonical_order(profile: str, target: str, events: list[dict[str, object]]) -> bool:
    if target == "retained":
        rows = [event for event in events if event.get("label", event.get("case")) == "retained"]
        return rl00bc_resource_oracle.ordered(rows, _RETAINED[profile])
    names = tuple(
        f"{part}-{boundary}"
        for part in ("setup", "call", "teardown")
        for boundary in ("start", "end")
    )
    return rl00bc_resource_oracle.ordered(events, names)


def _resource(
    profile: str,
    target: str,
    events: list[dict[str, object]],
    strict: dict[str, object],
    gaps: list[str],
) -> dict[str, object]:
    event = _entry(profile, target, events)
    if event is None:
        gaps.append("phase-entry event is absent or ambiguous")
        return {"entry_available": False, "own_memory_after_entry": False}
    leaf = rl00bc_resource_oracle.leaf(event, strict, profile)
    if leaf["bound"] is not True:
        gaps.append("phase-entry cgroup membership or inode cannot be bound to the supervisor leaf")
    elif leaf["native_inode_unavailable"] is True:
        gaps.append("native cgroup inode unavailable; stable supervisor inode and membership used")
    boundary, window = rl00bc_phase_window.select(profile, target, events, event, strict)
    memory = rl00bc_resource_oracle.memory(
        event,
        strict,
        boundary=boundary,
        boundary_is_valid=window["valid"] is True,
    )
    kernel = strict.get("kernel")
    raw = cast(dict[str, object], kernel) if isinstance(kernel, dict) else {}
    own_memory = raw.get("resource_violation") == "own-memory"
    proved = own_memory and leaf["bound"] is True and memory["oom_growth_within_phase"] is True
    if own_memory and not proved:
        gaps.append("local OOM counter growth after phase entry is not established")
    return {
        "entry_available": True,
        "leaf": leaf,
        "memory": memory,
        "phase_window": window,
        "own_memory_after_entry": proved,
        "phase_entry": event,
    }


def _child(
    profile: str,
    canonical: list[dict[str, object]],
    strict: list[dict[str, object]],
    canonical_run: dict[str, object],
    strict_run: dict[str, object],
    gaps: list[str],
) -> dict[str, object]:
    native = rl00bc_resource_oracle.child(canonical, canonical_run, profile)
    protected = rl00bc_resource_oracle.child(strict, strict_run, profile)
    required = ("single_positive_pid", "child_membership_matches", "ready_before_allocation")
    if not all(native.get(key) is True for key in required) or not native.get(
        "allocation_completed_in_order"
    ):
        gaps.append("canonical child membership or completed allocation is not established")
    if not all(protected.get(key) is True for key in required):
        gaps.append("strict child membership before allocation is not established")
    for label, item in (("canonical", native), ("strict", protected)):
        parent_leaf = item.get("parent_leaf")
        if (
            not isinstance(parent_leaf, dict)
            or cast(dict[str, object], parent_leaf).get("bound") is not True
        ):
            gaps.append(f"{label} child parent leaf binding is unavailable")
    return {"canonical": native, "strict": protected}


def _attribution(
    target: str, evidence: dict[str, object], *, canonical_bound: bool, strict_bound: bool
) -> str:
    resource = evidence.get("resource")
    if target == "retained" or not canonical_bound or not strict_bound:
        return "unproved"
    if (
        evidence.get("canonical_complete") is not True
        or evidence.get("strict_phase_entered") is not True
        or not isinstance(resource, dict)
    ):
        return "unproved"
    if cast(dict[str, object], resource).get("own_memory_after_entry") is not True:
        return "unproved"
    if target == "child":
        return "own-memory-after-entry; child-membership-assessed-separately"
    return "own-memory-after-entry-in-finite-fixture"


def _result(
    identity: str,
    variant: str,
    target: str,
    strict: dict[str, object],
    binding: dict[str, object],
    evidence: dict[str, object],
    gaps: list[str],
) -> dict[str, object]:
    raw_kernel = strict.get("kernel")
    kernel = cast(dict[str, object], raw_kernel) if isinstance(raw_kernel, dict) else {}
    canonical_bound = binding["canonical_report_identity"] is True
    strict_bound = binding["strict_identity_bound"] is True
    return {
        "identity": identity,
        "variant": variant,
        "canonical_identity_bound": canonical_bound,
        "strict_identity_bound": strict_bound,
        "identity_binding": binding,
        "resource_classification": strict.get("classification"),
        "kernel_cause": kernel.get("cause"),
        "native_status": kernel.get("native_status"),
        "cleanup_complete": kernel.get("cleanup_complete"),
        "evidence": evidence,
        "gaps": gaps,
        "case_attribution": _attribution(
            target, evidence, canonical_bound=canonical_bound, strict_bound=strict_bound
        ),
    }


def _retained_details(
    canonical_rows: list[dict[str, object]],
    strict_events: list[dict[str, object]],
    profile: str,
    identity: str,
    variant: str,
    evidence: dict[str, object],
    gaps: list[str],
) -> list[dict[str, object]]:
    case_phases = _phases(canonical_rows, profile, identity, variant, retained=False)
    case = _retained_case_phases(case_phases, gaps)
    case["ordered"] = _canonical_order(profile, "native", canonical_rows)
    case["complete"] = case["complete"] is True and case["ordered"] is True
    evidence["canonical_case"] = case
    return [event for event in strict_events if event.get("label", event.get("case")) == "retained"]


def _binding(
    profile: str,
    identity: str,
    variant: str,
    canonical: dict[str, object],
    strict: dict[str, object],
    events: tuple[list[dict[str, object]], list[dict[str, object]]],
    gaps: list[str],
    *,
    strict_events_valid: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    canonical_events, strict_events = events
    canonical_bound = rl00bc_event_binding.report_has(canonical, identity, variant, single=False)
    strict_report = rl00bc_event_binding.report_has(strict, identity, variant, single=True)
    dart_binding = (
        rl00bc_dart_binding.compare(canonical, strict, identity, variant)
        if profile == "dart"
        else None
    )
    if dart_binding is not None:
        strict_report = strict_report and dart_binding["bound"] is True
    canonical_rows, strict_rows, binding = rl00bc_event_binding.select(
        profile,
        identity,
        variant,
        canonical_events,
        strict_events,
        canonical_bound,
        strict_report,
        strict_scope_valid=strict.get("selection_error") is None and strict_events_valid,
    )
    binding["dart_report_binding"] = dart_binding
    strict_bound = binding["strict_identity_bound"] is True
    if not canonical_bound:
        gaps.append("canonical exact native identity and variant unavailable")
    if not strict_bound:
        gaps.append("strict exact native identity and variant unavailable")
    return canonical_rows, strict_rows, binding


def _record_order(
    profile: str,
    target: str,
    events: list[dict[str, object]],
    evidence: dict[str, object],
    gaps: list[str],
) -> None:
    ordered = _canonical_order(profile, target, events)
    evidence["canonical_phases_ordered"] = ordered
    if not ordered:
        evidence["canonical_complete"] = False
        gaps.append("canonical phase completion order is unavailable or ambiguous")


def evaluate(
    profile: str,
    target: str,
    identity: str,
    variant: str,
    canonical: dict[str, object],
    strict: dict[str, object],
) -> dict[str, object]:
    """Return event and native-ID evidence independently of the kernel classification."""
    canonical_events, canonical_gaps = _events(canonical)
    strict_events, strict_gaps = _events(strict)
    gaps = [
        *(f"canonical: {gap}" for gap in canonical_gaps),
        *(f"strict: {gap}" for gap in strict_gaps),
    ]
    canonical_rows, strict_rows, binding = _binding(
        profile,
        identity,
        variant,
        canonical,
        strict,
        (canonical_events, strict_events),
        gaps,
        strict_events_valid=not strict_gaps,
    )
    retained = target == "retained"
    phase_canonical = canonical_events if retained else canonical_rows
    phase_strict = strict_events if retained else strict_rows
    shared: dict[str, object] | None = None
    if retained:
        phase_canonical, phase_strict, shared = rl00bc_shared_oracle.select(
            profile,
            canonical,
            strict,
            canonical_events,
            strict_events,
            canonical_rows,
        )
    canonical_phases = _phases(phase_canonical, profile, identity, variant, retained=retained)
    strict_phases = _phases(phase_strict, profile, identity, variant, retained=retained)
    evidence = _phase_evidence(profile, target, canonical_phases, strict_phases, gaps)
    evidence["event_files_valid"] = not canonical_gaps and not strict_gaps
    evidence["shared_fixture_contexts"] = shared
    _record_order(profile, target, phase_canonical, evidence, gaps)
    if retained:
        phase_strict = _retained_details(
            canonical_rows, phase_strict, profile, identity, variant, evidence, gaps
        )
    resource_events = [*phase_strict, *strict_rows] if retained else phase_strict
    evidence["resource"] = _resource(profile, target, resource_events, strict, gaps)
    if target == "child":
        evidence["child"] = _child(profile, canonical_rows, strict_rows, canonical, strict, gaps)
    gaps.append("no exact per-phase memory amount is inferred from cgroup counters")
    return _result(identity, variant, target, strict, binding, evidence, gaps)
