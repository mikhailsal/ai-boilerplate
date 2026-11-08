"""Unprivileged guardian inside an externally bounded systemd transient unit.

The external provider must enforce unit limits, backstop guardian death and
observe root absence and an unrelated sentinel. Absence observations are upper
bounds on removal time; this service cannot prove its own post-exit removal.
"""

from __future__ import annotations

import argparse
import os
import grp
import fcntl
import stat
import pwd
import re
import select
import subprocess
import time
import uuid
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, SHIM, load, save

MIB = 1024 * 1024
RESERVE = 3_000_000_000


def _timespan(value: str) -> float:
    units = {"us": 0.000001, "ms": 0.001, "s": 1, "min": 60, "h": 3600}
    pieces = re.findall(r"(\d+(?:\.\d+)?)(us|ms|min|s|h)", value)
    if not pieces or "".join(number + unit for number, unit in pieces) != value.replace(" ", ""):
        raise ValueError(f"unsupported systemd timespan: {value}")
    return sum(float(number) * units[unit] for number, unit in pieces)


def _backstop(unit: str, deadline: int) -> dict[str, str]:
    names = (
        "MemoryMax",
        "MemorySwapMax",
        "TasksMax",
        "Delegate",
        "KillMode",
        "SendSIGKILL",
        "OOMPolicy",
        "TimeoutStopUSec",
        "RuntimeMaxUSec",
        "User",
        "Group",
    )
    if deadline - time.monotonic_ns() < 2670 * 1_000_000_000:
        raise ValueError("unit startup exceeded thirty-second admission window")
    command = [
        "/usr/bin/systemctl",
        "show",
        unit,
        "--no-pager",
        *[f"--property={name}" for name in names],
    ]
    done = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=2,
        check=True,
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
    )
    if len(done.stdout) > 16384 or len(done.stderr) > 16384:
        raise ValueError("systemd property output too large")
    values = dict(line.split("=", 1) for line in done.stdout.decode().splitlines())
    expected = {
        "MemoryMax": str(4096 * MIB),
        "MemorySwapMax": "0",
        "TasksMax": "512",
        "Delegate": "yes",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
        "OOMPolicy": "continue",
    }
    if any(values.get(key) != value for key, value in expected.items()):
        raise ValueError("systemd backstop properties mismatch")
    if _timespan(values["TimeoutStopUSec"]) > 1 or _timespan(values["RuntimeMaxUSec"]) > 2660:
        raise ValueError("systemd backstop exceeds original deadline")
    user, group = values["User"], values["Group"]
    uid = int(user) if user.isdecimal() else pwd.getpwnam(user).pw_uid
    gid = int(group) if group.isdecimal() else grp.getgrnam(group).gr_gid
    if uid != os.getuid() or gid != os.getgid():
        raise ValueError("systemd unit identity mismatch")
    return values


def provider(mode: str, output: Path, deadline: int, unit: str, argv: list[str]) -> int:
    """Own only the current verified unit, and reap its work and control leaves."""
    if (
        os.getuid() == 0
        or not output.is_absolute()
        or not argv
        or not re.fullmatch(r"quality-rl00bc-[a-f0-9]{32}\.service", unit)
    ):
        raise ValueError("unprivileged provider, absolute output and coordinator required")
    if time.monotonic_ns() >= deadline - RESERVE:
        raise ValueError("insufficient original deadline")
    output.mkdir(parents=True, exist_ok=True)
    lock_path = output / "lifecycle.lock"
    guardian_lock = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    controller_lock = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
    lock_info = os.fstat(guardian_lock)
    if (
        not stat.S_ISREG(lock_info.st_mode)
        or lock_info.st_uid != os.getuid()
        or stat.S_IMODE(lock_info.st_mode) != 0o600
        or os.fstat(controller_lock).st_ino != lock_info.st_ino
    ):
        os.close(guardian_lock)
        os.close(controller_lock)
        raise ValueError("invalid lifecycle lock")
    root = Group.current()
    guard: Group | None = None
    control: Group | None = None
    work: Group | None = None
    child: subprocess.Popen[bytes] | None = None
    record: dict[str, object] = {
        "mode": mode,
        "deadline_ns": deadline,
        "success": False,
        "backstop_required": "external systemd control-group stop",
        "lifecycle_inode": lock_info.st_ino,
    }
    error: str | None = None
    try:
        if (
            root.read("memory.max") != str(4096 * MIB)
            or root.read("memory.swap.max") != "0"
            or root.read("pids.max") != "512"
        ):
            raise ValueError("current unit limits differ from required envelope")
        if root.path.name != unit:
            raise ValueError("current cgroup is not the declared UUID unit")
        record["systemd_properties"] = _backstop(unit, deadline)
        record["root_before"] = root.snapshot()
        guard = root.bare(uuid.uuid4().hex)
        guard.write("cgroup.procs", os.getpid())
        root.enable()
        guard.limit(96, 16)
        control = root.create(uuid.uuid4().hex, 96, 16)
        work_name = uuid.uuid4().hex
        if mode == "prepared":
            work = root.create(work_name, 3840, 480)
            work.enable()
        record.update(
            {
                "root": root.snapshot(),
                "guardian": guard.snapshot(),
                "controller_before": control.snapshot(),
                "work_before": work.snapshot() if work is not None else None,
                "time_namespace": str(Path("/proc/self/ns/time").readlink()),
                "time_offsets": Path("/proc/self/timens_offsets").read_text(),
            }
        )
        if any(
            int(value)
            for row in str(record["time_offsets"]).splitlines()
            for value in row.split()[1:]
        ):
            raise ValueError("nonzero time namespace offsets")
        save(output / "provider.json", record)
        fd = os.open("cgroup.procs", os.O_WRONLY | os.O_NOFOLLOW, dir_fd=control.fd)
        try:
            handoff = (
                ["--work-fd", str(work.fd)]
                if work is not None
                else ["--parent-fd", str(root.fd), "--work-name", work_name]
            )
            inherited = work.fd if work is not None else root.fd
            controller_env = {
                **os.environ,
                "RL00_LIFECYCLE_FD": str(controller_lock),
                "RL00_LIFECYCLE_INODE": str(lock_info.st_ino),
                "RL00_LIFECYCLE_CLOSING": str(output / "closing.json"),
            }
            child = subprocess.Popen(
                [
                    "/bin/sh",
                    "-c",
                    SHIM,
                    "rl00bc-control",
                    str(fd),
                    *argv,
                    *handoff,
                    "--lifecycle-fd",
                    str(controller_lock),
                    "--deadline-ns",
                    str(deadline),
                ],
                pass_fds=(fd, inherited, controller_lock),
                env=controller_env,
                stdin=subprocess.DEVNULL,
            )
        finally:
            os.close(fd)
        watched = os.pidfd_open(child.pid)
        try:
            while not select.select([watched], [], [], 0.02)[0]:
                if (
                    mode == "host"
                    and work is None
                    and (output / "work-registration.json").is_file()
                ):
                    registered = load(output / "work-registration.json")
                    if registered.get("name") != work_name:
                        raise ValueError("work registration name mismatch")
                    work = root.adopt(work_name)
                    if (
                        registered.get("inode") != work.inode
                        or work.read("memory.max") != str(3840 * MIB)
                        or work.read("pids.max") != "480"
                        or work.read("memory.swap.max") != "0"
                        or work.read("cgroup.procs")
                        or not {"memory", "pids"}
                        <= set(work.read("cgroup.subtree_control").split())
                    ):
                        raise ValueError("registered work branch mismatch")
                    record["work_before"] = work.snapshot()
                    save(
                        output / "work-ack.json",
                        {
                            "name": work_name,
                            "inode": work.inode,
                            "lifecycle_inode": lock_info.st_ino,
                        },
                    )
                if time.monotonic_ns() >= deadline - RESERVE:
                    record["stop_reason"] = "deadline"
                    break
            else:
                record["stop_reason"] = "controller-exit"
        finally:
            os.close(watched)
        record["controller_before_cleanup"] = control.snapshot()
        record["work_before_cleanup"] = work.snapshot() if work is not None else None
        if work is None:
            raise ValueError("work branch was not registered")
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        cleanup_errors: list[str] = []
        # Publish CLOSING under an independently opened lock, then release it
        # before killing or waiting for a controller blocked on that lock.
        closing_published = False
        try:
            while True:
                try:
                    fcntl.flock(guardian_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic_ns() >= deadline:
                        raise TimeoutError("lifecycle closing lock deadline")
                    time.sleep(0.005)
            try:
                save(
                    output / "closing.json",
                    {"closing_ns": time.monotonic_ns(), "lifecycle_inode": lock_info.st_ino},
                )
                closing_published = True
            finally:
                fcntl.flock(guardian_lock, fcntl.LOCK_UN)
        except BaseException as exc:
            cleanup_errors.append(f"closing: {type(exc).__name__}: {exc}")
        record["closing_published"] = closing_published
        if work is None and "work_name" in locals() and (root.path / work_name).exists():
            try:
                work = root.adopt(work_name)
            except BaseException as exc:
                cleanup_errors.append(f"adopt work: {type(exc).__name__}: {exc}")
        cleanup_order = (
            (("work", work), ("control", control))
            if closing_published
            else (("control", control), ("work", work))
        )
        for label, group in cleanup_order:
            if group is None:
                continue
            try:
                duration = group.kill()
                record[f"{label}_kill_seconds"] = duration
                record[f"{label}_after_kill"] = group.snapshot()
                group.remove()
                record[f"{label}_absent_observed_ns"] = time.monotonic_ns()
            except BaseException as exc:
                cleanup_errors.append(f"{label}: {type(exc).__name__}: {exc}")
        if child is not None:
            try:
                record["controller_native_status"] = child.wait(
                    timeout=max(0.001, min(1.0, (deadline - time.monotonic_ns()) / 1e9))
                )
            except BaseException as exc:
                cleanup_errors.append(f"controller wait: {type(exc).__name__}: {exc}")
        record["cleanup_errors"] = cleanup_errors
        record["error"] = error
        record["finished_ns"] = time.monotonic_ns()
        record["success"] = (
            error is None
            and not cleanup_errors
            and record.get("controller_native_status") == 0
            and record.get("stop_reason") == "controller-exit"
            and time.monotonic_ns() < deadline
        )
        try:
            save(output / "guardian.json", record)
        except BaseException:
            record["success"] = False
        if guard is not None:
            os.close(guard.fd)
        os.close(root.fd)
        os.close(controller_lock)
        os.close(guardian_lock)
    status = record.get("controller_native_status")
    if record["success"]:
        return 0
    if (
        isinstance(status, int)
        and status != 0
        and not cleanup_errors
        and error is None
        and record.get("stop_reason") == "controller-exit"
    ):
        return status if status > 0 else 128 - status
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("host", "prepared"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deadline-ns", type=int, required=True)
    parser.add_argument("--unit-name", required=True)
    parser.add_argument("coordinator", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.coordinator
    if command and command[0] == "--":
        command = command[1:]
    return provider(args.mode, args.output, args.deadline_ns, args.unit_name, command)


if __name__ == "__main__":
    raise SystemExit(main())
