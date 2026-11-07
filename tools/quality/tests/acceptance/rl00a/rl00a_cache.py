"""Cache attribution and file-reclaim evidence for the opt-in RL00a proof."""

from __future__ import annotations

import logging
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

from rl00a_cgroup import MIB, Group, counters, load, payload, sampled_wait, save, wait_ready

CACHE_BYTES = 40 * MIB


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
    for name in ("before", "memory_stat_before", "ancestors_before"):
        if name not in record:
            record[name] = None
            missing.append(f"{name}: not collected")
    if "after" not in record:
        observe(record, "after", group.snapshot)
    if "memory_stat_after" not in record:
        observe(record, "memory_stat_after", lambda: counters(group.read("memory.stat")))
    if "ancestors_after" not in record:
        observe(record, "ancestors_after", lambda: ancestor_snapshots(group))
    record["child_live"] = None
    if child is None:
        missing.append("child was not launched")
    else:
        count = len(missing)
        observe(record, "native_poll_status", child.poll)
        if len(missing) == count:
            record["child_live"] = record["native_poll_status"] is None
    save_observation(output, record)


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


def ancestor_snapshots(group: Group) -> list[dict[str, object]]:
    snapshots: list[dict[str, object]] = []
    parent = group.parent
    while parent is not None:
        snapshots.append(parent.snapshot())
        parent = parent.parent
    return snapshots


def event_delta(before: dict[str, object], after: dict[str, object], name: str) -> int:
    old = cast(dict[str, int], before["memory.events.local"])[name]
    new = cast(dict[str, int], after["memory.events.local"])[name]
    assert new >= old, "resource event counters moved backwards"
    return new - old


def verify_ancestors(record: dict[str, object]) -> None:
    before = cast(list[dict[str, object]], record["ancestors_before"])
    after = cast(list[dict[str, object]], record["ancestors_after"])
    assert len(before) == len(after) == 3
    for old, new in zip(before, after, strict=True):
        assert (old["path"], old["inode"]) == (new["path"], new["inode"])
        for field in ("memory.max", "memory.swap.max", "pids.max"):
            assert old[field] == new[field]
        assert event_delta(old, new, "oom") == event_delta(old, new, "oom_kill") == 0


def phase_snapshot(
    child: subprocess.Popen[bytes],
    group: Group,
    ready: Path,
    phase: str,
    record: dict[str, object],
) -> dict[str, object]:
    stop_ns = int(cast(int, record["payload_stop_ns"]))
    while time.monotonic_ns() < stop_ns:
        current = int(group.read("memory.current"))
        record["sampled_peak_bytes"] = max(int(cast(int, record["sampled_peak_bytes"])), current)
        stats = counters(group.read("memory.stat"))
        record["sampled_file_peak_bytes"] = max(
            int(cast(int, record["sampled_file_peak_bytes"])), stats["file"]
        )
        evidence = load(ready)
        if evidence.get("phase") == phase:
            assert child.poll() is None, "file descriptor was not retained live"
            return {
                "payload": evidence,
                "leaf": group.snapshot(),
                "memory_stat": stats,
                "observed_ns": time.monotonic_ns(),
            }
        assert child.poll() is None, f"cache child exited before {phase}"
        time.sleep(0.002)
    message = f"cache phase {phase} did not finish before the original deadline"
    raise AssertionError(message)


def reclaim_checkpoints(
    child: subprocess.Popen[bytes],
    group: Group,
    output: Path,
    record: dict[str, object],
) -> None:
    ready = output / "payload.json"
    stop_ns = int(cast(int, record["payload_stop_ns"]))
    for phase, barrier in (("written", "read.barrier"), ("reread", "close.barrier")):
        record[phase] = phase_snapshot(child, group, ready, phase, record)
        save_observation(output, record)
        assert not record["missing_diagnostics"], record["missing_diagnostics"]
        assert time.monotonic_ns() < stop_ns, "file observation exhausted payload budget"
        (output / barrier).touch()


def verify_file_evidence(record: dict[str, object], output: Path) -> None:
    written = cast(dict[str, object], record["written"])
    reread = cast(dict[str, object], record["reread"])
    first = cast(dict[str, object], written["payload"])
    second = cast(dict[str, object], reread["payload"])
    old_file = cast(dict[str, object], first["file_observation"])
    new_file = cast(dict[str, object], second["file_observation"])
    assert first["bytes_written"] == second["bytes_read"] == CACHE_BYTES
    assert first["fsync_count"] == second["fsync_count"] == 10
    for evidence in (old_file, new_file):
        assert evidence["regular_file"] is True and evidence["links"] == 0
        assert evidence["size_bytes"] == CACHE_BYTES
        assert int(cast(int, evidence["allocated_bytes"])) >= CACHE_BYTES
        assert 0 <= int(cast(int, evidence["resident_bytes"])) < CACHE_BYTES
    assert (old_file["device"], old_file["inode"]) == (new_file["device"], new_file["inode"])
    first_stats = cast(dict[str, int], written["memory_stat"])
    second_stats = cast(dict[str, int], reread["memory_stat"])
    baseline = cast(dict[str, int], record["memory_stat_before"])
    assert baseline["file"] == 0 and int(cast(int, record["sampled_file_peak_bytes"])) > 0
    assert first_stats["file"] > 0 and first_stats["shmem"] == second_stats["shmem"] == 0
    assert second_stats["workingset_refault_file"] > first_stats["workingset_refault_file"]
    assert second_stats["pgsteal"] > baseline["pgsteal"]
    complete = cast(dict[str, object], load(output / "payload.json")["completion"])
    assert complete["removed"] is True and complete["cache_mib"] == 40
    assert complete["bytes_written"] == complete["bytes_read"] == CACHE_BYTES
    assert complete["fsync_count"] == 10


def cache_verdict(record: dict[str, object], output: Path, *, reclaim: bool) -> str:
    assert not record["missing_diagnostics"], record["missing_diagnostics"]
    before = cast(dict[str, object], record["before"])
    after = cast(dict[str, object], record["after"])
    for snapshot in (before, after):
        assert snapshot["memory.max"] == str(32 * MIB) and snapshot["memory.swap.max"] == "0"
        assert snapshot["pids.max"] == "8"
    verify_ancestors(record)
    assert event_delta(before, after, "max") > 0
    own_oom = event_delta(before, after, "oom")
    own_kill = event_delta(before, after, "oom_kill")
    status = record["native_wait_status"]
    if not reclaim and status == -signal.SIGKILL:
        assert own_oom > 0 and own_kill > 0, "SIGKILL lacked matching own-leaf OOM"
        return "own-memory-violation"
    assert status == 0 and own_oom == own_kill == 0
    if reclaim:
        verify_file_evidence(record, output)
        return "successful-file-reclaim-is-not-violation"
    return "native-success"


def start_cache(
    group: Group, output: Path, record: dict[str, object], *, reclaim: bool
) -> subprocess.Popen[bytes]:
    observe(record, "mount", lambda: output_mount(output))
    record["before"] = group.snapshot()
    observe(record, "memory_stat_before", lambda: counters(group.read("memory.stat")))
    observe(record, "ancestors_before", lambda: ancestor_snapshots(group))
    ready = output / "payload.json"
    inputs = {"artifact_dir": str(output)}
    if reclaim:
        save(
            ready,
            {
                **inputs,
                "payload_stop_ns": record["payload_stop_ns"],
                "read_barrier": str(output / "read.barrier"),
                "close_barrier": str(output / "close.barrier"),
            },
        )
    else:
        save(ready, inputs)
    return payload(group, "cache-reclaim" if reclaim else "cache", ready, "40")


def run_cache(group: Group, output: Path, stop_ns: int, *, reclaim: bool) -> dict[str, object]:
    record: dict[str, object] = {
        "missing_diagnostics": [],
        "exception": None,
        "native_wait_status": None,
        "native_poll_status": None,
        "identity": None,
        "sampled_peak_bytes": 0,
        "sampled_file_peak_bytes": 0,
        "scenario": "cache-reclaim" if reclaim else "dirty-cache",
        "payload_stop_ns": stop_ns,
    }
    child = None
    try:
        ready = output / "payload.json"
        child = start_cache(group, output, record, reclaim=reclaim)
        until = time.monotonic() + 1
        while "cgroup" not in load(ready) and time.monotonic() < until:
            time.sleep(0.005)
        record["identity"] = wait_ready(child, ready, group)
        if reclaim:
            mount = cast(dict[str, str], record["mount"])
            assert mount["filesystem"] not in {"tmpfs", "ramfs", "hugetlbfs"}
            reclaim_checkpoints(child, group, output, record)
        status, high = sampled_wait(child, group, stop_ns)
        record["native_wait_status"] = status
        record["native_observed_ns"] = time.monotonic_ns()
        assert record["native_observed_ns"] < stop_ns, (
            "native exit was not observed before the original payload stop"
        )
        record["sampled_peak_bytes"] = max(int(cast(int, record["sampled_peak_bytes"])), high)
        observe(record, "after", group.snapshot)
        observe(record, "memory_stat_after", lambda: counters(group.read("memory.stat")))
        observe(record, "ancestors_after", lambda: ancestor_snapshots(group))
        save_observation(output, record)
        record["observed_verdict"] = cache_verdict(record, output, reclaim=reclaim)
    except BaseException as error:
        record["exception"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        conclude_observation(output, group, child, record)
    return record
