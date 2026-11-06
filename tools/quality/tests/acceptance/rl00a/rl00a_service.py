"""Separate provider, bounded guardian and unprivileged RL00a supervisor."""

from __future__ import annotations

import os
import select
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import cast

from rl00a_cases import CASES, DEATH_CASES, Case, arm_death, event
from rl00a_cgroup import HERE, Group, load, save


def invocation(root: Group, name: str, mode: str) -> Group:
    if mode == "host":
        group = root.create(name, 224, 48)
    else:
        group = root.adopt(name)
        assert group.read("memory.max") == str(224 * 1024 * 1024)
        assert group.read("pids.max") == "48"
        assert group.read("memory.swap.max") == "0"
        assert {"memory", "pids"} <= set(group.read("cgroup.subtree_control").split())
    return group


def supervisor(args: list[str]) -> int:
    descriptor, name, mode, scenario, raw_output, raw_deadline = args
    root = Group(int(descriptor), Path(f"/proc/self/fd/{descriptor}").readlink())
    output = Path(raw_output)
    group = invocation(root, name, mode)
    control = group.bare(uuid.uuid4().hex)
    control.write("cgroup.procs", os.getpid())
    group.enable()
    control.limit(32, 8)
    work = group.create(uuid.uuid4().hex, 160, 32)
    work.enable()
    deadline_ns = int(raw_deadline)
    case = Case(group, control, work, output, deadline_ns)
    save(
        output / "registered.json", {"invocation": group.snapshot(), "control": control.snapshot()}
    )
    until = time.monotonic() + 1
    while not (output / "ack.json").exists() and time.monotonic() < until:
        time.sleep(0.005)
    assert (output / "ack.json").exists(), "guardian must acknowledge ownership before payload"
    assert str(Path("/proc/self/ns/time").readlink()) == load(output / "ack.json")["time_namespace"]
    assert time.monotonic_ns() < deadline_ns - 2_000_000_000
    if scenario in DEATH_CASES:
        arm_death(case, scenario)
    result = CASES[scenario](case)
    save(output / "case.json", {"scenario": scenario, "result": result})
    return 0


def root_setup(output: Path, name: str, mode: str) -> tuple[Group, Group]:
    root = Group.current()
    assert os.getuid() != 0, "test runner must be unprivileged"
    assert root.read("memory.max") == str(256 * 1024 * 1024)
    assert root.read("memory.swap.max") == "0" and root.read("pids.max") == "64"
    guard = root.bare(uuid.uuid4().hex)
    guard.write("cgroup.procs", os.getpid())
    root.enable()
    guard.limit(32, 8)
    if mode == "prepared":
        prepared = root.create(name, 224, 48)
        prepared.enable()
        os.close(prepared.fd)
    offsets = Path("/proc/self/timens_offsets").read_text()
    assert all(int(value) == 0 for row in offsets.splitlines() for value in row.split()[1:])
    save(
        output / "provider.json",
        {
            "root": root.snapshot(),
            "guardian": guard.snapshot(),
            "time_namespace": str(Path("/proc/self/ns/time").readlink()),
            "time_offsets": offsets,
            "mountinfo": [
                line
                for line in Path("/proc/self/mountinfo").read_text().splitlines()
                if " - cgroup2 " in line
            ],
            "provisioning": mode,
            "independent_enforcer": (
                "pidfd guardian; systemd control-group stop and runtime backstop"
            ),
        },
    )
    return root, guard


def start_supervisor(root: Group, args: list[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, str(HERE / "rl00a_service.py"), "supervisor", str(root.fd), *args],
        pass_fds=(root.fd,),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=sys.stderr,
    )


def observe(child: subprocess.Popen[bytes], root: Group, args: list[str]) -> tuple[str, int]:
    name, _mode, scenario, raw_output, raw_deadline = args
    output = Path(raw_output)
    payload_stop_ns = int(raw_deadline) - 2_000_000_000
    watched = os.pidfd_open(child.pid)
    reason = "native-exit"
    try:
        while not select.select([watched], [], [], 0.005)[0]:
            if (output / "registered.json").exists() and not (output / "ack.json").exists():
                group = root.adopt(name)
                registered = cast(dict[str, object], load(output / "registered.json")["invocation"])
                assert str(group.path) == registered["path"]
                assert group.inode == registered["inode"]
                os.close(group.fd)
                save(
                    output / "ack.json",
                    {"time_namespace": str(Path("/proc/self/ns/time").readlink())},
                )
            if (output / "armed.json").exists() and scenario in {"supervisor-death", "interrupt"}:
                reason = scenario
                sig = signal.SIGKILL if scenario == "supervisor-death" else signal.SIGINT
                signal.pidfd_send_signal(watched, sig)
                break
            if (output / "armed.json").exists() and scenario == "guardian-death":
                save(output / "outer-ready.json", {"pid": os.getpid(), "root": str(root.path)})
            if time.monotonic_ns() >= payload_stop_ns:
                reason = "deadline"
                break
        return reason, time.monotonic_ns()
    finally:
        os.close(watched)


def finish(root: Group, child: subprocess.Popen[bytes], args: list[str], reason: str) -> None:
    name, _mode, scenario, raw_output, raw_deadline = args
    output = Path(raw_output)
    group = root.adopt(name)
    before_cleanup = group.snapshot()
    registered = cast(dict[str, object], load(output / "registered.json")["control"])
    control = group.adopt(Path(str(registered["path"])).name)
    assert control.inode == registered["inode"]
    control_before_cleanup = control.snapshot()
    os.close(control.fd)
    cleanup = group.kill()
    status = child.wait(timeout=0.3)
    after_cleanup = group.snapshot()
    group.remove()
    save(
        output / "guardian.json",
        {
            "scenario": scenario,
            "reason": reason,
            "supervisor_native": status,
            "before_cleanup": before_cleanup,
            "control_before_cleanup": control_before_cleanup,
            "after_cleanup": after_cleanup,
            "cleanup_seconds": cleanup,
            "removed": not group.path.exists(),
            "original_deadline_ns": int(raw_deadline),
            "finished_ns": time.monotonic_ns(),
            "guardian_survived": True,
        },
    )
    if scenario not in DEATH_CASES:
        assert status == 0 and (output / "case.json").exists(), "supervisor did not prove its case"
    elif scenario == "control-oom":
        assert reason == "native-exit" and status == -signal.SIGKILL
        assert event(control_before_cleanup, "memory.events.local", "oom") > 0
        assert event(control_before_cleanup, "memory.events.local", "oom_kill") > 0
        assert event(before_cleanup, "memory.events.local", "oom") == 0
    elif scenario == "timeout":
        assert reason == "deadline" and status == -signal.SIGKILL
    else:
        assert reason == scenario and status != 0
    assert time.monotonic_ns() < int(raw_deadline), "cleanup exceeded original session deadline"
    assert cleanup < 2 and after_cleanup["cgroup.events"] == {"populated": 0, "frozen": 0}


def provider(args: list[str]) -> int:
    mode, scenario, raw_output = args
    output = Path(raw_output)
    name = uuid.uuid4().hex
    root, guard = root_setup(output, name, mode)
    deadline_ns = time.monotonic_ns() + 6_000_000_000
    arguments = [name, mode, scenario, str(output), str(deadline_ns)]
    child = start_supervisor(root, arguments)
    try:
        reason, _observed = observe(child, root, arguments)
        finish(root, child, arguments, reason)
    finally:
        if child.poll() is None:
            root.adopt(name).kill()
            child.wait(timeout=1)
        if (root.path / name).exists():
            remaining = root.adopt(name)
            remaining.kill()
            remaining.remove()
        root.write("cgroup.subtree_control", "-memory -pids")
        root.write("cgroup.procs", os.getpid())
        guard.remove()
        os.close(root.fd)
    return 0


if __name__ == "__main__":
    if sys.flags.optimize:
        message = "RL00a safety assertions require unoptimized Python"
        raise RuntimeError(message)
    if sys.argv[1] == "supervisor":
        raise SystemExit(supervisor(sys.argv[2:]))
    raise SystemExit(provider(sys.argv[1:]))
