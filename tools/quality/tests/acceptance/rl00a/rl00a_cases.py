"""Observable RL00a regressions; these are not production resource policy."""

from __future__ import annotations

import errno
import logging
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from rl00a_cgroup import CGROUP, MIB, Group, counters, load, payload, sampled_wait, save, wait_ready


@dataclass
class Case:
    invocation: Group
    control: Group
    work: Group
    output: Path
    deadline_ns: int

    def leaf(self, mib: int, tasks: int = 8) -> Group:
        return self.work.create(uuid.uuid4().hex, mib, tasks)


def event(snapshot: dict[str, object], field: str, counter: str) -> int:
    return cast(dict[str, int], snapshot[field])[counter]


def placement(case: Case) -> dict[str, object]:
    group = case.leaf(32)
    before = group.snapshot()
    ready = case.output / "payload.json"
    child = payload(group, "memory", ready, "1")
    identity = wait_ready(child, ready, group)
    status, high = sampled_wait(child, group, case.deadline_ns - 2_000_000_000)
    assert status == 0
    assert int(str(before["memory.max"])) == 32 * MIB
    assert before["memory.swap.max"] == "0"
    assert int(cast(int, identity["monotonic_ns"])) < case.deadline_ns
    assert not case.invocation.read("cgroup.procs")
    return {"before_exec": before, "identity": identity, "native": status, "sampled_peak": high}


def partial_setup(case: Case) -> dict[str, object]:
    with os.scandir(case.work.fd) as entries:
        before = sorted(entry.name for entry in entries)
    for name, mib, tasks in ((uuid.uuid4().hex, 161, 8), ("../foreign", 32, 8)):
        try:
            case.work.create(name, mib, tasks)
        except AssertionError:
            continue
        message = "invalid setup was admitted"
        raise AssertionError(message)
    with os.scandir(case.work.fd) as entries:
        assert sorted(entry.name for entry in entries) == before
    partial = case.leaf(32)
    partial.write("cgroup.subtree_control", "+pids")
    try:
        partial.create(uuid.uuid4().hex, 16, 2)
    except FileNotFoundError:
        pass
    else:
        message = "missing memory controller allowed payload setup"
        raise AssertionError(message)
    assert not (case.output / "payload.json").exists()
    return {"rejected_before_payload": True, "partial_groups_require_cleanup": 2}


def own_memory(case: Case) -> dict[str, object]:
    group = case.leaf(32)
    before = group.snapshot()
    ready = case.output / "payload.json"
    child = payload(group, "memory", ready, "80")
    identity = wait_ready(child, ready, group)
    status, high = sampled_wait(child, group, case.deadline_ns - 2_000_000_000)
    after = group.snapshot()
    assert status == -signal.SIGKILL
    assert event(after, "memory.events.local", "oom") > event(before, "memory.events.local", "oom")
    assert event(after, "memory.events.local", "oom_kill") > 0
    assert event(case.invocation.snapshot(), "memory.events.local", "oom") == 0
    return {
        "expected_verdict": "own-memory-violation",
        "identity": identity,
        "native": status,
        "before": before,
        "after": after,
        "sampled_peak_bytes": high,
        "sampled_overshoot_bytes": max(0, high - 32 * MIB),
        "peak_quality": "sampled-lower-bound",
    }


def ancestor_memory(case: Case) -> dict[str, object]:
    parent = case.leaf(96, 16)
    parent.enable()
    left = parent.create(uuid.uuid4().hex, 64, 8)
    right = parent.create(uuid.uuid4().hex, 64, 8)
    before = parent.snapshot()
    start = case.output / "start.barrier"
    release = case.output / "release.barrier"
    for side in ("left", "right"):
        save(
            case.output / f"{side}.json",
            {"start_barrier": str(start), "hold_barrier": str(release)},
        )
    first = payload(left, "memory", case.output / "left.json", "50")
    wait_ready(first, case.output / "left.json", left)
    second = payload(right, "memory", case.output / "right.json", "50")
    wait_ready(second, case.output / "right.json", right)
    start.touch()
    until = time.monotonic() + 2
    high = 0
    while first.poll() is None and second.poll() is None and time.monotonic() < until:
        high = max(high, int(parent.read("memory.current")))
        time.sleep(0.002)
    assert first.poll() is not None or second.poll() is not None, "ancestor did not enforce cap"
    release.touch()
    second_status = second.wait(timeout=0.5)
    first_status = first.wait(timeout=0.5)
    after = parent.snapshot()
    leaves = [left.snapshot(), right.snapshot()]
    assert -signal.SIGKILL in (first_status, second_status)
    assert event(after, "memory.events.local", "oom") > event(before, "memory.events.local", "oom")
    assert all(event(leaf, "memory.events.local", "max") == 0 for leaf in leaves)
    assert event(case.control.snapshot(), "memory.events.local", "oom") == 0
    return {
        "expected_verdict": "ancestor-memory-violation-no-case-attribution",
        "before": before,
        "after": after,
        "leaves": leaves,
        "native": [first_status, second_status],
        "sampled_peak_bytes": high,
    }


def caught_task_denial(case: Case) -> dict[str, object]:
    group = case.leaf(32, 2)
    before = group.snapshot()
    ready = case.output / "payload.json"
    child = payload(group, "fork-denial", ready)
    identity = wait_ready(child, ready, group)
    status, _high = sampled_wait(child, group, case.deadline_ns - 2_000_000_000)
    after = group.snapshot()
    complete = cast(dict[str, object], load(ready)["completion"])
    assert status == 0
    assert complete["denial_errno"] == errno.EAGAIN
    assert event(after, "pids.events", "max") > event(before, "pids.events", "max")
    return {
        "expected_verdict": "caught-own-task-denial-is-violation",
        "native": status,
        "identity": identity,
        "completion": complete,
        "before": before,
        "after": after,
    }


def output_mount(output: Path) -> dict[str, str]:
    """Identify the deepest mount containing the resolved output directory."""
    target = output.resolve()
    device_id = target.stat().st_dev
    device = f"{os.major(device_id)}:{os.minor(device_id)}"
    matches: list[tuple[int, dict[str, str]]] = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        fields, filesystem = left.split(), right.split()
        mountpoint = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), fields[4])
        path = Path(mountpoint)
        if fields[2] == device and (target == path or path in target.parents):
            matches.append(
                (
                    len(path.parts),
                    {
                        "mountpoint": mountpoint,
                        "filesystem": filesystem[0],
                        "device": device,
                        "source": filesystem[1],
                        "mountinfo": line,
                    },
                )
            )
    if not matches:
        message = f"no mount found for {target}"
        raise ValueError(message)
    return max(matches, key=lambda item: item[0])[1]


def observe(record: dict[str, object], name: str, read: Callable[[], object]) -> None:
    try:
        record[name] = read()
    except Exception as error:
        logging.exception("Could not capture cache diagnostic %s", name)
        record[name] = None
        cast(list[str], record["missing_diagnostics"]).append(f"{name}: {error!r}")


def save_observation(output: Path, record: dict[str, object]) -> None:
    try:
        save(output / "cache-observation.json", record)
    except Exception as error:
        logging.exception("Could not save cache observation")
        cast(list[str], record["missing_diagnostics"]).append(f"save: {error!r}")
        print(f"could not save cache observation: {error!r}; {record!r}", file=sys.stderr)


def finish_observation(
    output: Path, group: Group, child: subprocess.Popen[bytes] | None, record: dict[str, object]
) -> None:
    missing = cast(list[str], record["missing_diagnostics"])
    for name in ("before", "memory_stat_before"):
        if name not in record:
            record[name] = None
            missing.append(f"{name}: not collected")
    if "after" not in record:
        observe(record, "after", group.snapshot)
    if "memory_stat_after" not in record:
        observe(record, "memory_stat_after", lambda: counters(group.read("memory.stat")))
    record["child_live"] = None
    if child is None:
        missing.append("child was not launched")
    else:
        count = len(missing)
        observe(record, "native_poll_status", child.poll)
        if len(missing) == count:
            record["child_live"] = record["native_poll_status"] is None
    save_observation(output, record)


def assert_cache_events(case: Case, before: dict[str, object], after: dict[str, object]) -> None:
    assert event(after, "memory.events.local", "oom") == 0
    assert event(after, "memory.events.local", "max") > event(before, "memory.events.local", "max")
    assert not list(case.output.glob("rl00a-cache-*"))


def conclude_observation(
    output: Path, group: Group, child: subprocess.Popen[bytes] | None, record: dict[str, object]
) -> None:
    active_error = sys.exc_info()[0] is not None
    try:
        finish_observation(output, group, child, record)
    except Exception:
        logging.exception("Could not finish cache observation")
        if not active_error:
            raise
    if record["missing_diagnostics"] and not active_error:
        message = f"missing cache diagnostics: {record['missing_diagnostics']}"
        raise AssertionError(message)


def cache_reclaim(case: Case) -> dict[str, object]:
    group = case.leaf(32)
    observation: dict[str, object] = {
        "missing_diagnostics": [],
        "exception": None,
        "native_wait_status": None,
        "native_poll_status": None,
        "identity": None,
        "sampled_peak_bytes": None,
    }
    child = None
    try:
        observe(observation, "mount", lambda: output_mount(case.output))
        before = group.snapshot()
        observation["before"] = before
        observe(observation, "memory_stat_before", lambda: counters(group.read("memory.stat")))
        ready = case.output / "payload.json"
        save(ready, {"artifact_dir": str(case.output)})
        child = payload(group, "cache", ready, "40")
        until = time.monotonic() + 1
        while "cgroup" not in load(ready) and time.monotonic() < until:
            time.sleep(0.005)
        identity = wait_ready(child, ready, group)
        observation["identity"] = identity
        status, high = sampled_wait(child, group, case.deadline_ns - 2_000_000_000)
        observation["native_wait_status"] = status
        observation["sampled_peak_bytes"] = high
        observe(observation, "after", group.snapshot)
        observe(observation, "memory_stat_after", lambda: counters(group.read("memory.stat")))
        after = cast(dict[str, object], observation["after"])
        save_observation(case.output, observation)
        assert status == 0
        assert not observation["missing_diagnostics"], observation["missing_diagnostics"]
        assert_cache_events(case, before, after)
    except BaseException as error:
        observation["exception"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        conclude_observation(case.output, group, child, observation)

    return {
        "expected_verdict": "successful-reclaim-is-not-violation",
        "identity": identity,
        "native": status,
        "before": before,
        "after": after,
        "sampled_peak_bytes": high,
    }


def nested_budgets(case: Case) -> dict[str, object]:
    first = case.leaf(96, 16)
    first.enable()
    live_parent = first.create(uuid.uuid4().hex, 32, 8)
    second = first.create(uuid.uuid4().hex, 64, 8)
    second.enable()
    leaf = second.create(uuid.uuid4().hex, 32, 4)
    parent = payload(live_parent, "hold", case.output / "parent.json")
    wait_ready(parent, case.output / "parent.json", live_parent)
    ready = case.output / "payload.json"
    child = payload(leaf, "memory", ready, "80")
    identity = wait_ready(child, ready, leaf)
    status, _high = sampled_wait(child, leaf, case.deadline_ns - 2_000_000_000)
    rejected = time.monotonic_ns()
    try:
        second.create(uuid.uuid4().hex, 65, 9)
    except AssertionError:
        pass
    else:
        message = "nested command enlarged ancestor ceilings"
        raise AssertionError(message)
    assert time.monotonic_ns() - rejected < 100_000_000
    assert status == -signal.SIGKILL and parent.poll() is None
    assert int(live_parent.read("pids.current")) == 1
    assert int(first.read("memory.current")) >= int(live_parent.read("memory.current")) > 0
    assert int(cast(int, identity["monotonic_ns"])) < case.deadline_ns
    parent_cleanup = live_parent.kill()
    parent.wait(timeout=0.2)
    return {
        "expected_verdict": "nested-own-memory-violation-with-live-parent-charged",
        "original_deadline_ns": case.deadline_ns,
        "deadline_enforcement": "independent ancestor guardian; see nested timeout case",
        "boundaries": [first.snapshot(), second.snapshot(), leaf.snapshot()],
        "parent_cleanup_seconds": parent_cleanup,
        "native": status,
    }


def arm_death(case: Case, name: str) -> None:
    if name == "timeout":
        first = case.leaf(96, 16)
        first.enable()
        second = first.create(uuid.uuid4().hex, 64, 8)
        second.enable()
        group = second.create(uuid.uuid4().hex, 32, 4)
    else:
        group = case.leaf(32)
    child = payload(group, "hold", case.output / "payload.json")
    identity = wait_ready(child, case.output / "payload.json", group)
    assert identity["cgroup"] != f"0::/{case.control.path.relative_to(CGROUP)}\n"
    assert identity["session_id"] == identity["pid"]
    save(
        case.output / "armed.json",
        {
            "scenario": name,
            "payload": identity,
            "boundary": group.snapshot(),
            "requested_new_deadline_ns": time.monotonic_ns() + 60_000_000_000,
            "effective_ancestor_deadline_ns": case.deadline_ns,
        },
    )
    if name == "control-oom":
        blocks: list[bytearray] = []
        for _ in range(80):
            block = bytearray(MIB)
            for offset in range(0, MIB, 4096):
                block[offset] = 1
            blocks.append(block)
    time.sleep(8)
    message = "independent enforcer did not stop the supervisor"
    raise AssertionError(message)


CASES = {
    "placement": placement,
    "partial-setup": partial_setup,
    "own-memory": own_memory,
    "ancestor-memory": ancestor_memory,
    "nested-budgets": nested_budgets,
    "caught-task-denial": caught_task_denial,
    "cache-reclaim": cache_reclaim,
}
DEATH_CASES = ("interrupt", "timeout", "supervisor-death", "control-oom", "guardian-death")
