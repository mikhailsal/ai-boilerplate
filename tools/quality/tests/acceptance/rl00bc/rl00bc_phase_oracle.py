"""Compare emitted fixture phases without inferring case attribution from a kill."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

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
    for path in Path(directory).glob("*.json"):
        try:
            if path.stat().st_size > 16_384:
                gaps.append(f"oversized event: {path.name}")
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


def _binding(run: dict[str, object], identity: str, variant: str, *, single: bool) -> bool:
    value = run.get("native_cases")
    if not isinstance(value, list):
        return False
    rows = cast(list[object], value)
    if single and len(rows) != 1:
        return False
    matches: list[dict[str, object]] = []
    for row in rows:
        if isinstance(row, dict):
            case = cast(dict[str, object], row)
            if case.get("id") == identity and case.get("variant", "default") == variant:
                matches.append(case)
    return len(matches) == 1


def _case_name(profile: str, identity: str, variant: str) -> str:
    if profile in ("python", "php"):
        return variant
    if profile == "dart":
        return identity.removesuffix(" case")
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
    elif profile in ("python", "php"):
        required = {
            f"{part}-{boundary}"
            for part in ("setup", "call", "teardown")
            for boundary in ("start", "end")
        }
        canonical_complete = required <= canonical
        entered = f"{phase}-start" in strict
    else:
        canonical_complete = False
        entered = phase in strict
        gaps.append("producer emits coarse phase entries, not phase completion boundaries")
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


def _retained_case_phases(profile: str, phases: set[str], gaps: list[str]) -> dict[str, object]:
    if profile not in ("python", "php"):
        gaps.append("canonical case completion cannot be derived from coarse phase events")
        return {"phases": sorted(phases), "complete": None}
    required = {
        f"{part}-{boundary}"
        for part in ("setup", "call", "teardown")
        for boundary in ("start", "end")
    }
    complete = required <= phases
    if not complete:
        gaps.append("canonical retained case phases are incomplete")
    return {"phases": sorted(phases), "complete": complete}


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
    canonical_bound = _binding(canonical, identity, variant, single=False)
    strict_bound = _binding(strict, identity, variant, single=True)
    if not canonical_bound:
        gaps.append("canonical exact native identity and variant unavailable")
    if not strict_bound:
        gaps.append("strict exact native identity and variant unavailable")
    retained = target == "retained"
    canonical_phases = _phases(canonical_events, profile, identity, variant, retained=retained)
    strict_phases = _phases(strict_events, profile, identity, variant, retained=retained)
    evidence = _phase_evidence(profile, target, canonical_phases, strict_phases, gaps)
    if retained:
        case_phases = _phases(canonical_events, profile, identity, variant, retained=False)
        evidence["canonical_case"] = _retained_case_phases(profile, case_phases, gaps)
    if target == "child":
        gaps.append("owned child membership has not been independently observed")
    gaps.append("phase event and resource event ordering has not been established")
    return {
        "identity": identity,
        "variant": variant,
        "canonical_identity_bound": canonical_bound,
        "strict_identity_bound": strict_bound,
        "resource_classification": strict.get("classification"),
        "evidence": evidence,
        "gaps": gaps,
        "case_attribution": "unproved",
    }
