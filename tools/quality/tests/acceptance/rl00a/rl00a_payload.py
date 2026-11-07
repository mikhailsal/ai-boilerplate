"""Bounded payloads used by the opt-in RL00a cgroup feasibility probe."""

from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

MIB = 1024 * 1024
MAX_MIB = 80
MAX_CHILDREN = 16
MAX_SLEEP_SECONDS = 8


def _positive_mib(value: str) -> int:
    mib = int(value)
    if not 1 <= mib <= MAX_MIB:
        message = f"MIB must be between 1 and {MAX_MIB}"
        raise ValueError(message)
    return mib


def _identity() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "cgroup": Path("/proc/self/cgroup").read_text(encoding="utf-8"),
        "monotonic_ns": time.monotonic_ns(),
        "time_namespace": str(Path("/proc/self/ns/time").readlink()),
        "session_id": os.getsid(0),
        "process_group": os.getpgrp(),
        "uid": os.getuid(),
    }


def _existing(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        message = "READY_PATH must contain a JSON object when pre-created"
        raise TypeError(message)
    return cast(dict[str, Any], value)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    finally:
        with suppress(FileNotFoundError):
            Path(temporary).unlink()


def _ready(path: Path) -> dict[str, Any]:
    record = _existing(path)
    record.update(_identity())
    _write_json(path, record)
    return record


def _complete(path: Path, record: dict[str, Any], **fields: Any) -> None:
    current = _existing(path)
    if current != record:
        message = "READY_PATH changed while the payload was running"
        raise RuntimeError(message)
    record["completion"] = {"monotonic_ns": time.monotonic_ns(), **fields}
    _write_json(path, record)


def _barrier(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        message = "barrier must be a path string"
        raise TypeError(message)
    deadline = time.monotonic() + 3
    while not Path(value).exists() and time.monotonic() < deadline:
        time.sleep(0.005)
    if not Path(value).exists():
        message = "barrier was not released within 3 seconds"
        raise TimeoutError(message)


def _memory(path: Path, mib: int) -> int:
    record = _ready(path)
    _barrier(record.get("start_barrier"))

    blocks: list[bytearray] = []
    for _ in range(mib):
        block = bytearray(MIB)
        for offset in range(0, MIB, 4096):
            block[offset] = 1
        blocks.append(block)

    hold_barrier = record.get("hold_barrier")
    if hold_barrier is not None:
        _complete(path, record, allocated_mib=len(blocks))
        _barrier(hold_barrier)
        return 0

    time.sleep(1)
    return 0 if len(blocks) == mib else 1


def _hold(path: Path) -> int:
    if os.getpgrp() != os.getpid():
        os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    record = _ready(path)
    time.sleep(MAX_SLEEP_SECONDS)
    _complete(path, record, survived=True)
    return 0


def _fork_denial(path: Path) -> int:
    record = _ready(path)
    children: list[int] = []
    denial_errno: int | None = None
    try:
        while len(children) < MAX_CHILDREN:
            try:
                child = os.fork()
            except OSError as error:
                denial_errno = error.errno
                break
            if child == 0:
                time.sleep(MAX_SLEEP_SECONDS)
                os._exit(0)
            children.append(child)
    finally:
        for child in children:
            with suppress(ProcessLookupError):
                os.kill(child, signal.SIGKILL)
        for child in children:
            with suppress(ChildProcessError):
                os.waitpid(child, 0)
    _complete(path, record, denial_errno=denial_errno, children=len(children))
    return 0


def _cache(path: Path, mib: int) -> int:
    record = _ready(path)
    artifact_dir = record.get("artifact_dir")
    if not isinstance(artifact_dir, str) or not artifact_dir:
        message = "READY_PATH must include the parent-provided artifact_dir"
        raise ValueError(message)
    directory = Path(artifact_dir)
    if not directory.is_dir():
        message = "artifact_dir must be an existing directory"
        raise ValueError(message)
    record["phase"] = "writing"
    _write_json(path, record)
    with tempfile.TemporaryFile(mode="w+b", dir=directory) as stream:
        block = bytes(MIB)
        for _ in range(mib):
            stream.write(block)
        stream.flush()
        record["phase"] = "fsync"
        _write_json(path, record)
        os.fsync(stream.fileno())
        record["phase"] = "reading"
        _write_json(path, record)
        stream.seek(0)
        while stream.read(MIB):
            pass
    record["phase"] = "closed"
    _write_json(path, record)
    _complete(path, record, cache_mib=mib, removed=True)
    return 0


def _required_path(record: dict[str, Any], key: str) -> Path:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        msg = f"{key} must be a nonempty path string"
        raise ValueError(msg)
    return Path(value)


def _reclaim_inputs(record: dict[str, Any]) -> tuple[Path, int, Path, Path]:
    directory = _required_path(record, "artifact_dir")
    deadline = record.get("payload_stop_ns")
    if not directory.is_dir():
        msg = "artifact_dir must be an existing directory"
        raise ValueError(msg)
    if (
        isinstance(deadline, bool)
        or not isinstance(deadline, int)
        or deadline <= time.monotonic_ns()
    ):
        msg = "payload_stop_ns must be a future monotonic deadline"
        raise ValueError(msg)
    return (
        directory,
        deadline,
        _required_path(record, "read_barrier"),
        _required_path(record, "close_barrier"),
    )


def _reclaim_wait(barrier: Path, deadline: int) -> None:
    while True:
        if time.monotonic_ns() >= deadline:
            msg = "payload deadline expired while waiting for barrier"
            raise TimeoutError(msg)
        if barrier.exists():
            return
        time.sleep(0.005)


def _file_observation(descriptor: int) -> dict[str, Any]:
    # ACCESS_COPY supplies an address for mincore without dirtying the file.
    import ctypes
    import mmap
    import stat

    info = os.fstat(descriptor)
    page_size = os.sysconf("SC_PAGE_SIZE")
    page_count = (info.st_size + page_size - 1) // page_size
    with mmap.mmap(descriptor, info.st_size, access=mmap.ACCESS_COPY) as mapping:
        address = ctypes.c_char.from_buffer(mapping)
        try:
            vector = (ctypes.c_ubyte * page_count)()
            libc = ctypes.CDLL(None, use_errno=True)
            mincore = libc.mincore
            mincore.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_ubyte))
            mincore.restype = ctypes.c_int
            if mincore(ctypes.addressof(address), info.st_size, vector) != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
            resident = sum(1 for page in vector if page & 1) * page_size
        finally:
            del address
    return {
        "device": info.st_dev,
        "inode": info.st_ino,
        "links": info.st_nlink,
        "regular_file": stat.S_ISREG(info.st_mode),
        "size_bytes": info.st_size,
        "allocated_bytes": info.st_blocks * 512,
        "page_size": page_size,
        "resident_bytes": min(resident, info.st_size),
    }


def _cache_reclaim(path: Path, mib: int) -> int:
    record = _ready(path)
    directory, deadline, read_barrier, close_barrier = _reclaim_inputs(record)
    bytes_written = 0
    fsync_count = 0
    bytes_read = 0
    with tempfile.TemporaryFile(mode="w+b", dir=directory) as stream:
        block = bytes([0xA5]) * MIB
        for index in range(mib):
            written = stream.write(block)
            if written != len(block):
                msg = "short cache payload write"
                raise OSError(msg)
            bytes_written += written
            if (index + 1) % 4 == 0 or index + 1 == mib:
                stream.flush()
                os.fsync(stream.fileno())
                fsync_count += 1
        record.update(
            phase="written",
            bytes_written=bytes_written,
            fsync_count=fsync_count,
            file_observation=_file_observation(stream.fileno()),
        )
        _write_json(path, record)
        _reclaim_wait(read_barrier, deadline)
        stream.seek(0)
        while chunk := stream.read(MIB):
            bytes_read += len(chunk)
        if bytes_read != bytes_written:
            msg = "cache payload reread length differs from write length"
            raise OSError(msg)
        record.update(
            phase="reread",
            bytes_read=bytes_read,
            file_observation=_file_observation(stream.fileno()),
        )
        _write_json(path, record)
        _reclaim_wait(close_barrier, deadline)
    record["phase"] = "closed"
    _write_json(path, record)
    _complete(
        path,
        record,
        cache_mib=mib,
        removed=True,
        bytes_written=bytes_written,
        bytes_read=bytes_read,
        fsync_count=fsync_count,
    )
    return 0


def main(arguments: list[str]) -> int:
    if len(arguments) not in (2, 3):
        message = "usage: rl00a_payload.py ACTION READY_PATH [MIB]"
        raise ValueError(message)
    action, raw_path, *values = arguments
    path = Path(raw_path)
    sized_actions = {"memory": _memory, "cache": _cache, "cache-reclaim": _cache_reclaim}
    simple_actions = {"hold": _hold, "fork-denial": _fork_denial}
    if action in sized_actions and len(values) == 1:
        return sized_actions[action](path, _positive_mib(values[0]))
    if action in simple_actions and not values:
        return simple_actions[action](path)
    message = "invalid action or argument count"
    raise ValueError(message)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"rl00a payload: {error}", file=sys.stderr)
        raise SystemExit(2) from error
