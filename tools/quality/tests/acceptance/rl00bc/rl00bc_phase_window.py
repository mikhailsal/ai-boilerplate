"""Bound resource evidence by an observed phase end or the interrupted native run."""

from __future__ import annotations

from tests.acceptance.rl00bc import rl00bc_resource_oracle, rl00bc_shared_oracle


def names(profile: str, target: str) -> tuple[str, str]:
    if target == "retained":
        return rl00bc_shared_oracle.PHASES[profile]
    if target == "child":
        return "child-allocation-start", "child-allocation-end"
    phase = target if target in ("setup", "teardown") else "call"
    return f"{phase}-start", f"{phase}-end"


def _advanced(target: str, events: list[dict[str, object]]) -> bool:
    subsequent = {
        "retained": ("setup-start", "setup-end", "call-start", "call-end", "teardown-start", "teardown-end"),
        "setup": ("call-start", "call-end", "teardown-start", "teardown-end"),
        "teardown": (),
        "child": ("call-end", "teardown-start", "teardown-end"),
    }.get(target, ("teardown-start", "teardown-end"))
    return any(event.get("phase") in subsequent for event in events)


def select(profile: str, target: str, events: list[dict[str, object]],
           entry: dict[str, object], run: dict[str, object],
           ) -> tuple[dict[str, object] | None, dict[str, object]]:
    """An absent end is usable only while no later fixture phase was observed."""
    start, end = names(profile, target)
    matches = [event for event in events if event.get("phase") == end]
    boundary = matches[0] if len(matches) == 1 else None
    if matches:
        valid = len(matches) == 1 and rl00bc_resource_oracle.ordered([entry, *matches], (start, end))
        membership = rl00bc_resource_oracle.leaf(boundary, run, profile) if boundary is not None else {}
        valid = valid and membership.get("bound") is True
        return boundary, {"valid": valid, "end_event_count": len(matches),
                          "end_phase": end, "end_leaf": membership,
                          "scope": "observed entry-to-end counter interval"}
    advanced = _advanced(target, events)
    return None, {"valid": not advanced, "end_event_count": 0, "end_phase": end,
                  "later_phase_observed": advanced,
                  "scope": "open phase until kernel stop; no exact native phase-end time"}
