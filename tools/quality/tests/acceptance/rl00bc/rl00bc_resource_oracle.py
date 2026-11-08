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


def memory(event: dict[str, object], run: dict[str, object]) -> dict[str, object]:
    """Compare real local OOM counters at phase entry and around the run."""
    kernel = _mapping(run.get("kernel"))
    before, after = _mapping(kernel.get("before")), _mapping(kernel.get("after"))
    obs = _mapping(event.get("resource_observation"))
    baseline = obs.get("memory_events_local")
    result: dict[str, object] = {}
    proved = False
    for key in ("oom", "oom_kill"):
        first = _counter(before.get("memory.events.local"), key)
        entry = _counter(baseline, key)
        last = _counter(after.get("memory.events.local"), key)
        growth = (
            first is not None and entry is not None and last is not None and first <= entry < last
        )
        result[key] = {"before": first, "entry": entry, "after": last, "grew_after_entry": growth}
        proved = proved or growth
    return {"oom_growth_after_entry": proved, "counters": result}


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
