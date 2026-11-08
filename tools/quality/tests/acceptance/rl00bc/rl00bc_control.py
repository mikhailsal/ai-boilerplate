"""Verified controller handoff and finite preparation before native imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import NoReturn, cast

from tests.acceptance.rl00a.rl00a_cgroup import Group, load, save
from tests.acceptance.rl00bc import rl00bc_kernel, rl00bc_runtime, rl00bc_tools
from tests.acceptance.rl00bc.rl00bc_errors import invalid, unavailable

MIB = 1024 * 1024


def _descriptor(fd: int) -> Group:
    return Group(fd, Path(f"/proc/self/fd/{fd}").readlink())


def _host(args: argparse.Namespace, current: Group, provider: dict[str, object]) -> Group:
    parent = _descriptor(args.parent_fd)
    root = cast(dict[str, object], provider["root"])
    if parent.inode != root["inode"] or current.path.parent != parent.path:
        invalid("host handoff parent mismatch")
    group = parent.create(args.work_name, 3840, 480)
    group.enable()
    save(args.output / "work-registration.json", {"name": args.work_name, "inode": group.inode})
    until = min(args.deadline_ns - 3_000_000_000, time.monotonic_ns() + 2_000_000_000)
    while not (args.output / "work-ack.json").is_file() and time.monotonic_ns() < until:
        time.sleep(0.005)
    ack = load(args.output / "work-ack.json")
    lock = os.fstat(args.lifecycle_fd)
    if ack.get("inode") != group.inode or ack.get("lifecycle_inode") != lock.st_ino:
        invalid("guardian did not acknowledge the work identity")
    return group


def work_group(args: argparse.Namespace) -> Group:
    """Validate current control placement, work ownership and lifecycle authority."""
    provider = load(args.output / "provider.json")
    current = Group.current()
    try:
        control = cast(dict[str, object], provider["controller_before"])
        if current.inode != control["inode"] or current.read("memory.max") != str(96 * MIB):
            invalid("coordinator is outside its bounded control leaf")
        lock = os.fstat(args.lifecycle_fd)
        if lock.st_ino != provider["lifecycle_inode"] or lock.st_uid != os.getuid():
            invalid("lifecycle descriptor identity mismatch")
        group = (
            _descriptor(args.work_fd)
            if args.work_fd is not None
            else _host(args, current, provider)
        )
        expected = (str(3840 * MIB), "480", "0", "")
        actual = tuple(
            group.read(key) for key in ("memory.max", "pids.max", "memory.swap.max", "cgroup.procs")
        )
        if actual != expected:
            invalid("work handoff constraints mismatch")
        return group
    finally:
        os.close(current.fd)


def _prepare_command(
    work: Group,
    args: argparse.Namespace,
    index: int,
    request: tuple[Path, list[str], dict[str, str]],
) -> None:
    cwd, argv, environment = request
    result = rl00bc_kernel.execute(
        work,
        argv,
        cwd,
        environment,
        args.output / f"prepare-{index}",
        memory_mib=3072,
        tasks=256,
        native_seconds=600,
        ancestor_deadline_ns=args.deadline_ns,
    )
    if result.get("success") is not True or result.get("native_status") != 0:
        unavailable("bounded prerequisite preparation failed; see retained native evidence")


def prepare(work: Group, args: argparse.Namespace, repo: Path) -> dict[str, str]:
    """Bootstrap and materialize within the inherited finite envelope."""
    environment = {
        "HOME": str(Path.home()),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
    }
    _prepare_command(work, args, 0, (repo, [str(repo / "quality"), "bootstrap"], environment))
    requests = rl00bc_tools.materialization(repo, args.scratch / "prepared")
    for index, request in enumerate(requests, start=1):
        _prepare_command(work, args, index, request)
    resolved = rl00bc_tools.resolve(repo, args.scratch / "prepared")
    observed = rl00bc_runtime.probe(
        work, repo, args.output / "runtime-probes", resolved,
        ancestor_deadline_ns=args.deadline_ns,
    )
    if observed.get("status") != "verified":
        unavailable("prepared runtime identity could not be verified; see runtime probes")
    resolved["RL00_XDEBUG_LOADED"] = "1" if observed.get("xdebug_loaded") is True else "0"
    save(args.output / "runtime-paths.json", resolved)
    return resolved


def reexec(
    work: Group, args: argparse.Namespace, repo: Path, environment: dict[str, str]
) -> NoReturn:
    """Use the pinned core interpreter without restarting any deadline or provider."""
    for descriptor in (work.fd, args.lifecycle_fd):
        os.set_inheritable(descriptor, True)
    if args.parent_fd is not None:
        os.set_inheritable(args.parent_fd, False)
    command = [
        environment["RL00_PYTHON"],
        "-m",
        "tests.acceptance.rl00bc.rl00bc_driver",
        "--inside",
        "--runtime-ready",
        "--phase",
        args.phase,
        "--profile",
        args.profile,
        "--output",
        str(args.output),
        "--scratch",
        str(args.scratch),
        "--criterion",
        args.criterion,
        "--samples",
        str(args.samples),
        "--criterion-approval",
        args.criterion_approval,
        "--work-fd",
        str(work.fd),
        "--lifecycle-fd",
        str(args.lifecycle_fd),
        "--deadline-ns",
        str(args.deadline_ns),
    ]
    child_env = {**os.environ, "PYTHONPATH": str(repo / "tools/quality")}
    os.execve(command[0], command, child_env)  # noqa: S606 - preserve bounded exec ownership


def runtime(args: argparse.Namespace) -> dict[str, str]:
    """Read only the verified preparation record, never invent runtime paths."""
    result = load(args.output / "runtime-paths.json")
    if not result or not all(isinstance(value, str) for value in result.values()):
        invalid("invalid prepared runtime record")
    return cast(dict[str, str], result)


def context(args: argparse.Namespace, repo: Path, environment: dict[str, str]) -> dict[str, str]:
    """Bind the scope to committed source and prepared runtime inputs."""
    source = load(args.output / "identity.json")
    runtime_inputs = {
        "paths": environment,
        "observations": load(args.output / "runtime-probes/runtime.json"),
    }
    runtime_hash = hashlib.sha256(json.dumps(runtime_inputs, sort_keys=True).encode()).hexdigest()
    return {
        "RL00_CONTEXT_CANDIDATE": str(source["commit"]),
        "RL00_CONTEXT_BASE": str(source["base"]),
        "RL00_CONTEXT_TESTED_TREE": str(source["tree"]),
        "RL00_CONTEXT_POLICY": hashlib.sha256((repo / "quality.toml").read_bytes()).hexdigest(),
        "RL00_CONTEXT_RUNTIME": runtime_hash,
        "RL00_CONTEXT_SOURCE": str(source["source_digest"]),
    }
