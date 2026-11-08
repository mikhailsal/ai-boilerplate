"""Check native two-worker rendezvous without attributing memory to a case."""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import cast

from tests.acceptance.rl00bc.rl00bc_errors import invalid

MAX_FILES = 512
MAX_EVENT = 16384
MAX_MARKER = 128
PHASES = ("worker-ready", "worker-peer-observed", "worker-overlap-complete")
IDENTITY = re.compile(r"([1-9][0-9]*)(?::(-?[0-9]+))?")


def _read(path: Path, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            invalid(f"worker evidence file is not bounded: {path.name}")
        data = os.read(descriptor, limit + 1)
        if len(data) > limit or len(data) != info.st_size:
            invalid(f"worker evidence file changed while reading: {path.name}")
        return data
    finally:
        os.close(descriptor)


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        invalid("worker evidence is not an object")
    return cast(dict[str, object], value)


def _canonical(trial: dict[str, object]) -> None:
    if trial.get("scope") != "canonical-suite" or trial.get("workers") != 2:
        invalid("worker evidence does not belong to a two-worker canonical suite")
    kernel = _object(trial.get("kernel"))
    if trial.get("classification") != "observed-success":
        invalid("two-worker native execution did not succeed")
    if kernel.get("success") is not True or kernel.get("cleanup_complete") is not True:
        invalid("two-worker kernel execution or cleanup is incomplete")
    if kernel.get("resource_violation") is not None:
        invalid("two-worker kernel execution reported a resource violation")


def _directory(trial: dict[str, object]) -> Path:
    _canonical(trial)
    events, evidence = trial.get("events"), trial.get("kernel_evidence")
    if not isinstance(events, str) or not isinstance(evidence, str):
        invalid("worker evidence paths are missing")
    directory, kernel_path = Path(events), Path(evidence)
    if not directory.is_absolute() or directory.is_symlink() or not directory.is_dir():
        invalid("worker event directory is not an absolute owned directory")
    if kernel_path != directory.parent / "kernel/result.json" or directory.name != "events":
        invalid("worker event directory does not belong to this kernel record")
    return directory


def _identity(text: str, *, dart: bool) -> str:
    match = IDENTITY.fullmatch(text)
    if match is None or (match.group(2) is not None) != dart:
        invalid("invalid native worker identity")
    return text


def _markers(directory: Path, prefix: str, *, dart: bool) -> tuple[list[str], dict[str, str]]:
    identities: list[str] = []
    paths: dict[str, str] = {}
    for part in (0, 1):
        values: list[str] = []
        for kind in ("ready", "seen"):
            name = f"{prefix}-{kind}-{part}"
            path = directory / name
            paths[name] = str(path)
            values.append(_identity(_read(path, MAX_MARKER).decode("utf-8"), dart=dart))
        if values[0] != values[1]:
            invalid("worker ready and seen markers disagree")
        identities.append(values[0])
    if len(set(identities)) != 2:
        invalid("worker rendezvous did not identify two distinct native workers")
    return identities, paths


def _files(directory: Path, prefix: str) -> list[Path]:
    paths: list[Path] = []
    count = 0
    with os.scandir(directory) as entries:
        for entry in entries:
            count += 1
            if count > MAX_FILES:
                invalid("worker event directory exceeds its file bound")
            if entry.name.startswith((f"{prefix}-ready-", f"{prefix}-seen-")):
                expected = {f"{prefix}-{kind}-{part}" for kind in ("ready", "seen")
                            for part in (0, 1)}
                if entry.name not in expected:
                    invalid("unexpected worker rendezvous marker")
            if entry.name.endswith(".json"):
                paths.append(directory / entry.name)
    return sorted(paths)


def _events(
    directory: Path, labels: tuple[str, str], prefix: str
) -> dict[tuple[int, str], tuple[Path, dict[str, object]]]:
    found: dict[tuple[int, str], tuple[Path, dict[str, object]]] = {}
    for path in _files(directory, prefix):
        event = _object(json.loads(_read(path, MAX_EVENT)))
        phase = event.get("phase")
        if phase not in PHASES:
            continue
        label = event.get("label", event.get("case"))
        if label not in labels:
            invalid("worker rendezvous event has an unexpected label")
        part = labels.index(cast(str, label))
        key = (part, cast(str, phase))
        if key in found:
            invalid("duplicate worker rendezvous event")
        found[key] = (path, event)
    if len(found) != 6:
        invalid("worker rendezvous event sequence is incomplete")
    return found


def _event_identity(event: dict[str, object], profile: str, part: int) -> str:
    pid = event.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        invalid("worker event has no native process ID")
    if profile == "dart":
        worker = event.get("worker")
        if not isinstance(worker, str) or event.get("part") != part:
            invalid("Dart worker event has invalid isolate identity")
        if _identity(worker, dart=True).split(":", 1)[0] != str(pid):
            invalid("Dart worker isolate identity disagrees with its process ID")
        return worker
    return str(pid)


def _timestamp(event: dict[str, object], profile: str) -> int:
    value = event.get("monotonic_us" if profile == "dart" else "monotonic_ns")
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        invalid("worker event has invalid monotonic timestamp")
    return value


def _check_part(
    profile: str, part: int, identities: list[str],
    events: dict[tuple[int, str], tuple[Path, dict[str, object]]],
) -> list[str]:
    timestamps: list[int] = []
    paths: list[str] = []
    for phase in PHASES:
        path, event = events[(part, phase)]
        if _event_identity(event, profile, part) != identities[part]:
            invalid("worker event identity disagrees with rendezvous marker")
        expected_variant = f"gw{part}" if profile == "python" else (
            f"worker-{part}" if profile == "dart" else str(part)
        )
        if event.get("variant") != expected_variant:
            invalid("worker event variant disagrees with its rendezvous part")
        if phase != "worker-ready":
            peer = event.get("peer_worker" if profile == "dart" else "peer_pid")
            if str(peer) != identities[1 - part]:
                invalid("worker peer observation is not reciprocal")
        timestamps.append(_timestamp(event, profile))
        paths.append(str(path))
    if not timestamps[0] <= timestamps[1] <= timestamps[2]:
        invalid("worker rendezvous phases are not ordered within the worker")
    return paths


def evaluate(profile: str, trial: dict[str, object]) -> dict[str, object]:
    """Report observed worker overlap; this does not attribute cost to any case."""
    result: dict[str, object] = {
        "status": "unproved", "claim_limit": "worker overlap only; no case-memory attribution",
        "event_directory": trial.get("events"), "kernel_evidence": trial.get("kernel_evidence"),
    }
    try:
        if profile not in ("python", "dart", "node", "browser"):
            invalid("native two-worker rendezvous is unsupported for this profile")
        directory = _directory(trial)
        prefix = "node" if profile in ("node", "browser") else profile
        labels = ("gw0", "gw1") if profile == "python" else ("worker-0", "worker-1")
        result["marker_paths"] = {
            f"{prefix}-{kind}-{part}": str(directory / f"{prefix}-{kind}-{part}")
            for part in (0, 1) for kind in ("ready", "seen")
        }
        identities, markers = _markers(directory, prefix, dart=profile == "dart")
        result["worker_ids"] = identities
        events = _events(directory, labels, prefix)
        result["event_paths"] = [str(path) for path, _ in events.values()]
        paths = [_check_part(profile, part, identities, events) for part in (0, 1)]
        result.update({"status": "observed-overlap", "worker_ids": identities,
                       "marker_paths": markers, "event_paths": paths,
                       "basis": "reciprocal two-way ready/seen handshake"})
    except (OSError, ValueError, TypeError, KeyError) as error:
        result["error"] = f"{type(error).__name__}: {error}"[:1024]
    return result
