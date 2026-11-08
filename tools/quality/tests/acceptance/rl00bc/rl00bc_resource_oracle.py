"""Bind fixture observations to the supervisor's actual cgroup snapshots."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import cast

_CGROUP = Path("/sys/fs/cgroup")


def _mapping(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _inode(value: object) -> int | None:
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and value.isdecimal() and int(value) > 0:
        return int(value)
    return None


def _membership(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    lines = [line[3:] for line in value.splitlines() if line.startswith("0::")]
    return lines[0] if len(lines) == 1 and lines[0].startswith("/") else None


def _expected_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        relative = Path(value).relative_to(_CGROUP)
    except ValueError:
        return None
    return "/" + str(relative)


def leaf(event: dict[str, object], run: dict[str, object], profile: str) -> dict[str, object]:
    """Compare observed membership and inode with both kernel snapshots."""
    kernel = _mapping(run.get("kernel"))
    before, after = _mapping(kernel.get("before")), _mapping(kernel.get("after"))
    obs = _mapping(event.get("resource_observation"))
    before_inode, after_inode = _inode(before.get("inode")), _inode(after.get("inode"))
    event_inode = _inode(obs.get("cgroup_inode"))
    path, after_path = before.get("path"), after.get("path")
    expected = _expected_path(path)
    membership = _membership(obs.get("cgroup"))
    stable = before_inode is not None and before_inode == after_inode and path == after_path
    membership_match = expected is not None and membership == expected
    inode_match = event_inode is not None and event_inode == before_inode
    missing_dart_inode = profile == "dart" and obs.get("cgroup_inode") is None
    bound = stable and membership_match and (inode_match or missing_dart_inode)
    return {
        "bound": bound,
        "membership": membership,
        "expected_membership": expected,
        "supervisor_inode_before": before_inode,
        "supervisor_inode_after": after_inode,
        "native_inode": event_inode,
        "native_inode_unavailable": missing_dart_inode,
    }


def _counter(value: object, key: str) -> int | None:
    number = _mapping(value).get(key)
    return number if type(number) is int and number >= 0 else None


def _monotone_counter(
    first: int | None,
    entry: int | None,
    boundary: int | None,
    last: int | None,
) -> bool:
    if first is None or entry is None or boundary is None or last is None:
        return False
    return first <= entry <= boundary <= last


def _counter_evidence(
    key: str,
    before: object,
    entry: object,
    boundary: object,
    after: object,
) -> tuple[dict[str, object], bool, bool, bool]:
    first = _counter(before, key)
    middle = _counter(entry, key)
    end = _counter(boundary, key)
    last = _counter(after, key)
    growth = (
        first is not None and middle is not None and last is not None and first <= middle < last
    )
    monotone = _monotone_counter(first, middle, end, last)
    grew_to_boundary = middle is not None and end is not None and middle < end
    return (
        {
            "before": first,
            "entry": middle,
            "boundary": end,
            "after": last,
            "grew_after_entry": growth,
            "counter_increased_to_boundary": grew_to_boundary,
            "monotone_through_boundary": monotone,
        },
        growth,
        monotone,
        grew_to_boundary,
    )


def memory(
    event: dict[str, object],
    run: dict[str, object],
    *,
    boundary: dict[str, object] | None = None,
    boundary_is_valid: bool = True,
) -> dict[str, object]:
    """Retain run-wide growth and separately prove growth within a valid boundary."""
    kernel = _mapping(run.get("kernel"))
    before, after = _mapping(kernel.get("before")), _mapping(kernel.get("after"))
    obs = _mapping(event.get("resource_observation"))
    baseline = obs.get("memory_events_local")
    if boundary is None:
        boundary_source = "kernel-after-snapshot"
        boundary_observation = kernel.get("after")
        boundary_counters = after.get("memory.events.local")
    else:
        boundary_source = "native-boundary-event"
        boundary_observation = boundary.get("resource_observation")
        boundary_counters = _mapping(boundary_observation).get("memory_events_local")
    result: dict[str, object] = {}
    proved = False
    phase_complete = boundary_is_valid
    phase_growth = False
    for key in ("oom", "oom_kill"):
        evidence, growth, monotone, grew_to_boundary = _counter_evidence(
            key,
            before.get("memory.events.local"),
            baseline,
            boundary_counters,
            after.get("memory.events.local"),
        )
        result[key] = evidence
        proved = proved or growth
        phase_complete = phase_complete and monotone
        phase_growth = phase_growth or grew_to_boundary
    return {
        "oom_growth_after_entry": proved,
        "oom_growth_within_phase": phase_complete and phase_growth,
        "boundary_source": boundary_source,
        "boundary_supplied": boundary is not None,
        "boundary_is_valid": boundary_is_valid,
        "boundary_observation": boundary_observation,
        "phase_counter_evidence_valid": phase_complete,
        "counters": result,
    }


def _child_pids(events: list[dict[str, object]]) -> tuple[set[int], bool]:
    pids: set[int] = set()
    valid = bool(events)
    for event in events:
        value = event.get("child_pid")
        if type(value) is not int or value <= 0:
            valid = False
        else:
            pids.add(value)
    return pids, valid


def _clock(event: dict[str, object]) -> int | None:
    value = event.get("monotonic_ns", event.get("monotonic_us"))
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


def _same_clock(selected: list[dict[str, object]]) -> bool:
    pid = selected[0].get("pid")
    if type(pid) is not int or pid <= 0:
        return False
    if any(event.get("pid") != selected[0].get("pid") for event in selected):
        return False
    if any(event.get("worker") != selected[0].get("worker") for event in selected):
        return False
    return not any(
        ("monotonic_ns" in event) != ("monotonic_ns" in selected[0]) for event in selected
    )


def _increasing(times: list[int | None]) -> bool:
    return all(a is not None and b is not None and a <= b for a, b in pairwise(times))


def _ordered(events: list[dict[str, object]], names: tuple[str, ...]) -> bool:
    selected: list[dict[str, object]] = []
    for name in names:
        matches = [event for event in events if event.get("phase") == name]
        if len(matches) != 1:
            return False
        selected.append(matches[0])
    if not selected or not _same_clock(selected):
        return False
    times = [_clock(event) for event in selected]
    return _increasing(times)


def ordered(events: list[dict[str, object]], names: tuple[str, ...]) -> bool:
    """Compare timestamps only within one observed process and worker clock."""
    return _ordered(events, names)


def child(
    events: list[dict[str, object]], run: dict[str, object], profile: str
) -> dict[str, object]:
    """Check observed child PID, membership, and allocation boundaries."""
    relevant = [
        event
        for event in events
        if event.get("phase") in ("child-ready", "child-allocation-start", "child-allocation-end")
    ]
    pids, valid_pids = _child_pids(relevant)
    positive = valid_pids and len(pids) == 1
    phases = {str(event.get("phase")) for event in relevant}
    ready = [event for event in relevant if event.get("phase") == "child-ready"]
    kernel = _mapping(run.get("kernel"))
    before = _mapping(kernel.get("before"))
    expected = _expected_path(before.get("path"))
    same_group = (
        len(ready) == 1
        and expected is not None
        and (_membership(ready[0].get("child_cgroup")) == expected)
    )
    parent_leaf = leaf(ready[0], run, profile) if len(ready) == 1 else {"bound": False}
    return {
        "single_positive_pid": positive,
        "child_pids": sorted(pids),
        "child_membership_matches": same_group,
        "parent_leaf": parent_leaf,
        "phases": sorted(phases),
        "allocation_started": "child-allocation-start" in phases,
        "allocation_completed": "child-allocation-end" in phases,
        "ready_before_allocation": _ordered(relevant, ("child-ready", "child-allocation-start")),
        "allocation_completed_in_order": _ordered(
            relevant, ("child-ready", "child-allocation-start", "child-allocation-end")
        ),
    }
