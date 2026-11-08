"""Collect bounded RL00b/c evidence on CI; this is not a production test gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import select
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group, load, save
from tests.acceptance.rl00bc import (
    rl00bc_adoption,
    rl00bc_candidates,
    rl00bc_compat,
    rl00bc_correctness,
)
from tests.acceptance.rl00bc import rl00bc_kernel, rl00bc_measure, rl00bc_tools

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
MODULE = "tests.acceptance.rl00bc"
SECONDS = 2700
MIB = 1024 * 1024


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, check=True, capture_output=True, text=True, timeout=5
    ).stdout.strip()


def identity(output: Path) -> dict[str, object]:
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("experiment source must be a clean committed candidate")
    paths = [
        *HERE.glob("*.py"),
        HERE.parent / "rl00a/rl00a_cgroup.py",
        REPO / "docs/plan/test-resource-limits/rl00bc-protocol.md",
        REPO / ".github/workflows/resource-methods.yml",
        REPO / ".github/workflows/resource-methods-job.yml",
        REPO / "quality.toml",
        REPO / "tools/quality/toolchains.toml",
    ]
    paths.extend(
        REPO / relative
        for relative in (
            "tools/quality/uv.lock",
            "tools/quality/helpers/dart/pubspec.yaml",
            "tools/quality/helpers/dart/pubspec.lock",
            "tools/quality/helpers/php/composer.json",
            "tools/quality/helpers/php/composer.lock",
            "tools/quality/src/quality/testkit/browserseed/package-lock.json",
        )
    )
    hashes: dict[str, str] = {}
    for path in sorted(paths):
        if path.stat().st_size > 2 * MIB:
            raise ValueError("source input exceeds the declared capture bound")
        relative = str(path.relative_to(REPO))
        content = path.read_bytes()
        committed = subprocess.run(
            ["git", "show", f"HEAD:{relative}"],
            cwd=REPO,
            check=True,
            capture_output=True,
            timeout=5,
        ).stdout
        if content != committed:
            raise ValueError(f"source does not match candidate: {relative}")
        hashes[relative] = hashlib.sha256(content).hexdigest()
        target = output / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    result: dict[str, object] = {
        "commit": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "base": git("rev-parse", "HEAD^"),
        "source_sha256": hashes,
        "source_digest": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "libc": platform.libc_ver(),
        "controller_python": sys.version,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }
    save(output / "identity.json", result)
    return result


def unit(name: str, argv: list[str], *, sentinel: bool = False) -> list[str]:
    properties = {
        "User": str(os.getuid()),
        "Group": str(os.getgid()),
        "MemoryMax": "32M" if sentinel else "4096M",
        "MemorySwapMax": "0",
        "TasksMax": "8" if sentinel else "512",
        "RuntimeMaxSec": "3000s" if sentinel else "2660s",
        "TimeoutStopSec": "1s",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
        "OOMPolicy": "continue",
        "LimitCORE": "0",
    }
    if not sentinel:
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
        f"--working-directory={REPO}",
        f"--setenv=PYTHONPATH={REPO / 'tools/quality'}",
        *[f"--property={key}={value}" for key, value in properties.items()],
        *argv,
    ]


def stop(name: str) -> None:
    subprocess.run(
        ["sudo", "-n", "systemctl", "stop", name], capture_output=True, check=False, timeout=5
    )


def sentinel(name: str) -> tuple[subprocess.Popen[bytes], int]:
    proxy = subprocess.Popen(
        unit(name, ["/bin/sleep", "2990"], sentinel=True),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        until = time.monotonic() + 3
        while proxy.poll() is None and time.monotonic() < until:
            value = subprocess.run(
                ["sudo", "-n", "systemctl", "show", name, "--property=MainPID", "--value"],
                check=False,
                capture_output=True,
                text=True,
                timeout=1,
            ).stdout.strip()
            if value.isdecimal() and int(value):
                return proxy, os.pidfd_open(int(value))
            time.sleep(0.02)
        raise RuntimeError("independent sentinel did not start")
    except BaseException:
        stop(name)
        proxy.wait(timeout=3)
        raise


def outer(args: argparse.Namespace) -> int:
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.getuid() == 0:
        raise ValueError("heavy experiments require the approved unprivileged CI environment")
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    started = time.monotonic_ns()
    deadline = started + SECONDS * 1_000_000_000
    identity(output)
    name = f"quality-rl00bc-{uuid.uuid4().hex}"
    peer = f"quality-rl00bc-sentinel-{uuid.uuid4().hex}"
    proxy, watched = sentinel(peer)
    result: dict[str, object] = {
        "unit": name,
        "original_deadline_ns": deadline,
        "collector_complete": False,
        "integration_verdict": "unproved",
    }
    try:
        coordinator = [
            sys.executable,
            "-m",
            f"{MODULE}.rl00bc_driver",
            "--inside",
            "--phase",
            args.phase,
            "--profile",
            args.profile,
            "--output",
            str(output),
            "--scratch",
            str(args.scratch.absolute()),
            "--criterion",
            args.criterion,
            "--samples",
            str(args.samples),
        ]
        command = [
            sys.executable,
            "-m",
            f"{MODULE}.rl00bc_service",
            "--mode",
            args.mode,
            "--output",
            str(output),
            "--deadline-ns",
            str(deadline),
            "--unit-name",
            f"{name}.service",
            "--",
            *coordinator,
        ]
        with (output / "service.log").open("wb") as log:
            child = subprocess.Popen(
                unit(name, command), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT
            )
            try:
                status = child.wait(timeout=max(0.001, (deadline - time.monotonic_ns()) / 1e9))
            finally:
                if child.poll() is None:
                    stop(name)
                    child.wait(timeout=3)
        result["proxy_native_status"] = status
        provider = load(output / "provider.json")
        root = cast(dict[str, object], provider["root"])
        path = Path(str(root["path"]))
        if path.name != f"{name}.service":
            raise ValueError("provider returned a foreign root")
        while time.monotonic_ns() < deadline:
            try:
                if path.stat().st_ino != root["inode"]:
                    raise ValueError("service root identity changed")
            except FileNotFoundError:
                result["root_removed_observed_ns"] = time.monotonic_ns()
                break
            time.sleep(0.005)
        else:
            raise TimeoutError("owned service root was not removed before original deadline")
        alive = not select.select([watched], [], [], 0)[0] and proxy.poll() is None
        if alive:
            signal.pidfd_send_signal(watched, 0)
        result["sentinel_survived"] = alive
        guardian = load(output / "guardian.json")
        if status != 0 or guardian.get("success") is not True or not alive:
            raise RuntimeError("provider, collector or sentinel did not complete correctly")
        result["collector_complete"] = True
        return 0
    finally:
        result["finished_ns"] = time.monotonic_ns()
        active_error = sys.exc_info()[0] is not None
        try:
            save(output / "outer.json", result)
            stop(name)
            stop(peer)
            proxy.wait(timeout=3)
        except Exception:
            if not active_error:
                raise
        finally:
            os.close(watched)


def work_group(args: argparse.Namespace) -> Group:
    provider = load(args.output / "provider.json")
    current = Group.current()
    control = cast(dict[str, object], provider["controller_before"])
    if current.inode != control["inode"] or current.read("memory.max") != str(96 * MIB):
        raise ValueError("coordinator is outside its bounded control leaf")
    lock = os.fstat(args.lifecycle_fd)
    if lock.st_ino != provider["lifecycle_inode"] or lock.st_uid != os.getuid():
        raise ValueError("lifecycle descriptor identity mismatch")
    if args.work_fd is not None:
        group = Group(args.work_fd, Path(f"/proc/self/fd/{args.work_fd}").readlink())
    else:
        parent = Group(args.parent_fd, Path(f"/proc/self/fd/{args.parent_fd}").readlink())
        root = cast(dict[str, object], provider["root"])
        if parent.inode != root["inode"] or current.path.parent != parent.path:
            raise ValueError("host handoff parent mismatch")
        group = parent.create(args.work_name, 3840, 480)
        group.enable()
        save(args.output / "work-registration.json", {"name": args.work_name, "inode": group.inode})
        until = min(args.deadline_ns - 3_000_000_000, time.monotonic_ns() + 2_000_000_000)
        while not (args.output / "work-ack.json").is_file() and time.monotonic_ns() < until:
            time.sleep(0.005)
        ack = load(args.output / "work-ack.json")
        if ack.get("inode") != group.inode or ack.get("lifecycle_inode") != lock.st_ino:
            raise ValueError("guardian did not acknowledge the work identity")
    if (
        group.read("memory.max") != str(3840 * MIB)
        or group.read("pids.max") != "480"
        or group.read("memory.swap.max") != "0"
        or group.read("cgroup.procs")
    ):
        raise ValueError("work handoff constraints mismatch")
    os.close(current.fd)
    return group


def prepare(work: Group, args: argparse.Namespace) -> dict[str, str]:
    env = {"HOME": str(Path.home()), "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}
    bootstrap = rl00bc_kernel.execute(
        work,
        [str(REPO / "quality"), "bootstrap"],
        REPO,
        env,
        args.output / "prepare-0",
        memory_mib=3072,
        tasks=256,
        native_seconds=600,
        ancestor_deadline_ns=args.deadline_ns,
    )
    if bootstrap.get("success") is not True or bootstrap.get("native_status") != 0:
        raise RuntimeError("bounded bootstrap failed; see retained native evidence")
    requests = rl00bc_tools.materialization(REPO, args.scratch / "prepared")
    for index, (cwd, argv, environment) in enumerate(requests, start=1):
        raw = rl00bc_kernel.execute(
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
        if raw.get("success") is not True or raw.get("native_status") != 0:
            raise RuntimeError(
                "bounded prerequisite preparation failed; see retained native evidence"
            )
    resolved = rl00bc_tools.resolve(REPO, args.scratch / "prepared")
    save(args.output / "runtime-paths.json", resolved)
    return resolved


def inside(args: argparse.Namespace) -> int:
    group = work_group(args)
    try:
        environment = prepare(group, args)
        source = load(args.output / "identity.json")
        policy = hashlib.sha256((REPO / "quality.toml").read_bytes()).hexdigest()
        runtime = hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest()
        context = {
            "RL00_CONTEXT_CANDIDATE": str(source["commit"]),
            "RL00_CONTEXT_BASE": str(source["base"]),
            "RL00_CONTEXT_TESTED_TREE": str(source["tree"]),
            "RL00_CONTEXT_POLICY": policy,
            "RL00_CONTEXT_RUNTIME": runtime,
            "RL00_CONTEXT_SOURCE": str(source["source_digest"]),
        }
        if args.phase == "prepare":
            result: dict[str, object] = {"prepared": True}
        elif args.phase == "correctness":
            result = rl00bc_correctness.check(
                group,
                REPO,
                args.scratch / "corpus",
                args.output / "correctness",
                args.profile,
                {**environment, **context},
                ancestor_deadline_ns=args.deadline_ns,
            )
        elif args.phase == "compatibility":
            result = rl00bc_compat.reconcile(
                group,
                REPO,
                args.scratch / "corpus",
                args.output / "compatibility",
                args.profile,
                environment,
                ancestor_deadline_ns=args.deadline_ns,
            )
        elif args.phase == "candidates":
            result = rl00bc_candidates.prove(
                group,
                REPO,
                args.scratch / "candidates",
                args.output / "candidates",
                environment,
                ancestor_deadline_ns=args.deadline_ns,
            )
        elif args.phase == "adoption":
            result = rl00bc_adoption.adopt(
                group,
                REPO,
                args.scratch / "adoption",
                args.output / "adoption",
                environment,
                ancestor_deadline_ns=args.deadline_ns,
            )
        else:
            result = rl00bc_measure.measure(
                group,
                REPO,
                args.scratch / "corpus",
                args.output / "measurement",
                args.profile,
                environment,
                ancestor_deadline_ns=args.deadline_ns,
                samples=args.samples,
                criterion=args.criterion,
            )
        accepted = comparison_passed(args.phase, result)
        save(
            args.output / "phase.json",
            {
                "phase": args.phase,
                "result": result,
                "collection_complete": True,
                "comparison_passed": accepted,
                "stage_acceptance": "separate-audit-required",
            },
        )
        return 0 if accepted else 2
    finally:
        os.close(group.fd)


def comparison_passed(phase: str, result: dict[str, object]) -> bool:
    """Stop dependent jobs on a failed comparison; never certify integration."""
    return {
        "prepare": result.get("prepared") is True,
        "correctness": result.get("verdict") == "comparisons-passed-external-proofs-pending",
        "compatibility": result.get("verdict") == "pass",
        "candidates": result.get("success") is True,
        "measure": result.get("status") == "proposed-criteria-pass",
        "adoption": adoption_commands_passed(result),
    }[phase]


def adoption_commands_passed(result: dict[str, object]) -> bool:
    """Check observed commands while retaining unmeasured adoption requirements."""
    phases = result.get("phases")
    if not isinstance(phases, list) or not phases:
        return False
    return all(isinstance(item, dict) and item.get("success") is True for item in phases)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        required=True,
        choices=("prepare", "correctness", "compatibility", "candidates", "adoption", "measure"),
    )
    parser.add_argument(
        "--profile", choices=("dart", "node", "browser", "php", "python"), default="python"
    )
    parser.add_argument("--mode", choices=("host", "prepared"), default="host")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--criterion", choices=("A", "B"), default="A")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("--work-fd", type=int)
    parser.add_argument("--parent-fd", type=int)
    parser.add_argument("--work-name")
    parser.add_argument("--lifecycle-fd", type=int)
    parser.add_argument("--deadline-ns", type=int)
    args = parser.parse_args()
    if not 1 <= args.samples <= 100 or not args.scratch.is_absolute():
        parser.error("finite sample count and absolute scratch root required")
    return inside(args) if args.inside else outer(args)


if __name__ == "__main__":
    raise SystemExit(main())
