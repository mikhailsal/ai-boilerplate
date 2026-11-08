"""Provision only named, finite CI units and retain independent cleanup evidence."""

from __future__ import annotations

import logging
import os
import select
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import load, save
from tests.acceptance.rl00bc.rl00bc_errors import invalid, unavailable
from tests.acceptance.rl00bc.rl00bc_identity import capture

MODULE = "tests.acceptance.rl00bc"
RESERVE_NS = 3_000_000_000


@dataclass(frozen=True)
class Request:
    """The explicit, reviewable arguments to one remote collection phase."""

    repo: Path
    output: Path
    scratch: Path
    phase: str
    profile: str
    mode: str
    criterion: str
    samples: int
    criterion_approval: str = ""


def _unit(request: Request, name: str, argv: list[str], *, peer: bool = False) -> list[str]:
    properties = {
        "User": str(os.getuid()),
        "Group": str(os.getgid()),
        "MemoryMax": "32M" if peer else "4096M",
        "MemorySwapMax": "0",
        "TasksMax": "8" if peer else "512",
        "RuntimeMaxSec": "3000s" if peer else "2660s",
        "TimeoutStopSec": "1s",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
        "OOMPolicy": "continue",
        "LimitCORE": "0",
    }
    if not peer:
        properties["Delegate"] = "yes"
    return [
        "sudo",
        "-n",
        "systemd-run",
        "--quiet",
        "--wait",
        "--pipe",
        "--collect",
        f"--unit={name}",
        f"--working-directory={request.repo}",
        f"--setenv=PYTHONPATH={request.repo / 'tools/quality'}",
        *[f"--property={key}={value}" for key, value in properties.items()],
        *argv,
    ]


def _stop(name: str) -> None:
    subprocess.run(
        ["sudo", "-n", "systemctl", "stop", name], capture_output=True, check=False, timeout=5
    )


def _main_pid(name: str) -> int | None:
    value = subprocess.run(
        ["sudo", "-n", "systemctl", "show", name, "--property=MainPID", "--value"],
        check=False,
        capture_output=True,
        text=True,
        timeout=1,
    ).stdout.strip()
    return int(value) if value.isdecimal() and int(value) else None


def _peer(request: Request, name: str) -> tuple[subprocess.Popen[bytes], int]:
    command = _unit(request, name, ["/bin/sleep", "2990"], peer=True)
    proxy = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        until = time.monotonic() + 3
        while proxy.poll() is None and time.monotonic() < until:
            pid = _main_pid(name)
            if pid is not None:
                return proxy, os.pidfd_open(pid)
            time.sleep(0.02)
        unavailable("independent sentinel did not start")
    except BaseException:
        errors: list[str] = []
        _cleanup_call("sentinel stop", lambda: _stop(name), errors)
        _cleanup_call("sentinel proxy", lambda: proxy.wait(timeout=3), errors)
        raise


def _command(request: Request, name: str, deadline: int) -> list[str]:
    coordinator = [
        sys.executable,
        "-m",
        f"{MODULE}.rl00bc_driver",
        "--inside",
        "--phase",
        request.phase,
        "--profile",
        request.profile,
        "--output",
        str(request.output),
        "--scratch",
        str(request.scratch),
        "--criterion",
        request.criterion,
        "--samples",
        str(request.samples),
        "--criterion-approval",
        request.criterion_approval,
    ]
    provider = [
        sys.executable,
        "-m",
        f"{MODULE}.rl00bc_service",
        "--mode",
        request.mode,
        "--output",
        str(request.output),
        "--deadline-ns",
        str(deadline),
        "--unit-name",
        f"{name}.service",
        "--",
        *coordinator,
    ]
    return _unit(request, name, provider)


def _collect(request: Request, name: str, deadline: int) -> int:
    with (request.output / "service.log").open("wb") as log:
        child = subprocess.Popen(
            _command(request, name, deadline),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            remaining = max(0.001, (deadline - time.monotonic_ns()) / 1e9)
            return child.wait(timeout=remaining)
        finally:
            if child.poll() is None:
                _stop(name)
                child.wait(timeout=3)


def _absence(request: Request, name: str, deadline: int) -> int:
    provider = load(request.output / "provider.json")
    root = cast(dict[str, object], provider["root"])
    path = Path(str(root["path"]))
    if path.name != f"{name}.service":
        invalid("provider returned a foreign root")
    while time.monotonic_ns() < deadline:
        try:
            if path.stat().st_ino != root["inode"]:
                invalid("service root identity changed")
        except FileNotFoundError:
            observed = time.monotonic_ns()
            if observed <= deadline:
                return observed
            break
        time.sleep(0.005)
    message = "owned service root was not observed removed before its fixed cleanup deadline"
    raise TimeoutError(message)


def _timing_number(guardian: dict[str, object], key: str) -> int:
    value = guardian.get(key)
    if type(value) is not int:
        invalid("guardian cleanup timing is incomplete")
    return value


def _cleanup_deadline(guardian: dict[str, object], original: int) -> int:
    anchor = _timing_number(guardian, "cleanup_anchor_ns")
    started = _timing_number(guardian, "cleanup_started_ns")
    finished = _timing_number(guardian, "finished_ns")
    deadline = _timing_number(guardian, "cleanup_deadline_ns")
    if guardian.get("deadline_ns") != original or deadline != min(original, anchor + RESERVE_NS):
        invalid("guardian cleanup deadline does not match the original fixed reserve")
    if not 0 < anchor <= started <= finished <= time.monotonic_ns() or anchor > original:
        invalid("guardian cleanup timing is inconsistent")
    if guardian.get("cleanup_anchor_kind") not in ("controller-stop", "cleanup-start"):
        invalid("guardian cleanup anchor is unavailable")
    if guardian.get("success") is True and finished >= deadline:
        invalid("guardian reported success after the cleanup deadline")
    return deadline


def _save_observation(path: Path, result: dict[str, object]) -> str | None:
    try:
        save(path, result)
    except OSError as error:
        logging.exception("outer observation persistence failed")
        return f"{type(error).__name__}: {error}"
    return None


def _observe(
    request: Request, name: str, deadline: int, peer: tuple[subprocess.Popen[bytes], int]
) -> dict[str, object]:
    proxy, watched = peer
    status = _collect(request, name, deadline)
    guardian = load(request.output / "guardian.json")
    cleanup_deadline = _cleanup_deadline(guardian, deadline)
    result: dict[str, object] = {
        "proxy_native_status": status,
        "cleanup_anchor_ns": guardian["cleanup_anchor_ns"],
        "cleanup_deadline_ns": cleanup_deadline,
        "guardian_error": guardian.get("error"),
        "guardian_cleanup_errors": guardian.get("cleanup_errors"),
        "collector_complete": False,
    }
    observation_path = request.output / "outer-observation.json"
    metadata_error = _save_observation(observation_path, result)
    if metadata_error is not None:
        result["metadata_error"] = metadata_error
    removed = _absence(request, name, min(deadline, cleanup_deadline))
    alive = not select.select([watched], [], [], 0)[0] and proxy.poll() is None
    if alive:
        signal.pidfd_send_signal(watched, 0)
    result["root_removed_observed_ns"] = removed
    result["sentinel_survived"] = alive
    later_error = _save_observation(observation_path, result)
    if later_error is not None:
        result["metadata_error"] = later_error
    if status != 0 or guardian.get("success") is not True or not alive:
        unavailable("provider, collector or sentinel did not complete correctly")
    if metadata_error is not None or later_error is not None:
        unavailable("outer observation could not be persisted")
    result["collector_complete"] = True
    save(observation_path, result)
    return result


def _cleanup_call(label: str, operation: Callable[[], object], errors: list[str]) -> None:
    try:
        operation()
    except Exception as error:
        logging.exception("bounded cleanup operation failed: %s", label)
        errors.append(f"{label}: {type(error).__name__}: {error}")


def _finish(
    request: Request,
    names: tuple[str, str],
    peer: tuple[subprocess.Popen[bytes], int],
    result: dict[str, object],
) -> None:
    active = sys.exc_info()[0] is not None
    errors: list[str] = []
    for name in names:
        _cleanup_call("service stop", lambda name=name: _stop(name), errors)
    proxy, watched = peer
    _cleanup_call("sentinel proxy", lambda: proxy.wait(timeout=3), errors)
    _cleanup_call("sentinel pidfd", lambda: os.close(watched), errors)
    result.update(finished_ns=time.monotonic_ns(), cleanup_errors=errors)
    _cleanup_call("outer metadata", lambda: save(request.output / "outer.json", result), errors)
    if errors and not active:
        unavailable("provider cleanup failed; see retained cleanup errors")


def run(request: Request, here: Path) -> int:
    """Run an approved remote collector while preserving cleanup on every exit."""
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.getuid() == 0:
        invalid("heavy experiments require the approved unprivileged CI environment")
    request.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    deadline = time.monotonic_ns() + 2700 * 1_000_000_000
    capture(request.repo, here, request.output)
    name = f"quality-rl00bc-{uuid.uuid4().hex}"
    peer_name = f"quality-rl00bc-sentinel-{uuid.uuid4().hex}"
    peer = _peer(request, peer_name)
    result: dict[str, object] = {
        "unit": name,
        "original_deadline_ns": deadline,
        "collector_complete": False,
        "integration_verdict": "unproved",
    }
    try:
        result.update(_observe(request, name, deadline, peer))
        return 0
    finally:
        _finish(request, (name, peer_name), peer, result)
