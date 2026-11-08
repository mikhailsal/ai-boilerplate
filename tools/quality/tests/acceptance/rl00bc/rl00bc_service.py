"""Unprivileged guardian inside an externally bounded systemd transient unit.

The external provider must enforce unit limits, backstop guardian death and
observe root absence and an unrelated sentinel. Absence observations are upper
bounds on removal time; this service cannot prove its own post-exit removal.
"""

from __future__ import annotations

import argparse
import fcntl
import logging
import os
import re
import select
import stat
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import SHIM, Group, load, save
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid
from tests.acceptance.rl00bc.rl00bc_service_backstop import backstop

MIB = 1024 * 1024
RESERVE = 3_000_000_000


@dataclass
class _Guardian:
    mode: str
    output: Path
    deadline: int
    unit: str
    argv: list[str]
    root: Group
    guardian_lock: int
    controller_lock: int
    inode: int
    guard: Group | None = None
    control: Group | None = None
    work: Group | None = None
    child: subprocess.Popen[bytes] | None = None
    work_name: str | None = None
    error: str | None = None
    cleanup_deadline_ns: int | None = None
    cleanup_errors: list[str] = field(default_factory=list[str])
    record: dict[str, object] = field(default_factory=dict[str, object])

    def prepare(self) -> None:
        if (
            self.root.read("memory.max") != str(4096 * MIB)
            or self.root.read("memory.swap.max") != "0"
            or self.root.read("pids.max") != "512"
        ):
            invalid("current unit limits differ from required envelope")
        if self.root.path.name != self.unit:
            invalid("current cgroup is not the declared UUID unit")
        self.record["systemd_properties"] = backstop(self.unit, self.deadline)
        self.record["root_before"] = self.root.snapshot()
        self.guard = self.root.bare(uuid.uuid4().hex)
        self.guard.write("cgroup.procs", os.getpid())
        self.root.enable()
        self.guard.limit(96, 16)
        self.control = self.root.create(uuid.uuid4().hex, 96, 16)
        self.work_name = uuid.uuid4().hex
        if self.mode == "prepared":
            self.work = self.root.create(self.work_name, 3840, 480)
            self.work.enable()
        self.record.update(
            {
                "root": self.root.snapshot(),
                "guardian": self.guard.snapshot(),
                "controller_before": self.control.snapshot(),
                "work_before": self.work.snapshot() if self.work is not None else None,
                "time_namespace": str(Path("/proc/self/ns/time").readlink()),
                "time_offsets": Path("/proc/self/timens_offsets").read_text(),
            }
        )
        if any(
            int(value)
            for row in str(self.record["time_offsets"]).splitlines()
            for value in row.split()[1:]
        ):
            invalid("nonzero time namespace offsets")
        save(self.output / "provider.json", self.record)

    def start_controller(self) -> None:
        assert self.control is not None and self.work_name is not None
        fd = os.open("cgroup.procs", os.O_WRONLY | os.O_NOFOLLOW, dir_fd=self.control.fd)
        try:
            handoff = (
                ["--work-fd", str(self.work.fd)]
                if self.work is not None
                else ["--parent-fd", str(self.root.fd), "--work-name", self.work_name]
            )
            inherited = self.work.fd if self.work is not None else self.root.fd
            env = {
                **os.environ,
                "RL00_LIFECYCLE_FD": str(self.controller_lock),
                "RL00_LIFECYCLE_INODE": str(self.inode),
                "RL00_LIFECYCLE_CLOSING": str(self.output / "closing.json"),
            }
            self.child = subprocess.Popen(
                [
                    "/bin/sh",
                    "-c",
                    SHIM,
                    "rl00bc-control",
                    str(fd),
                    *self.argv,
                    *handoff,
                    "--lifecycle-fd",
                    str(self.controller_lock),
                    "--deadline-ns",
                    str(self.deadline),
                ],
                pass_fds=(fd, inherited, self.controller_lock),
                env=env,
                stdin=subprocess.DEVNULL,
            )
        finally:
            os.close(fd)

    def register_work(self) -> None:
        assert self.work_name is not None
        registered = load(self.output / "work-registration.json")
        if registered.get("name") != self.work_name:
            invalid("work registration name mismatch")
        self.work = self.root.adopt(self.work_name)
        if (
            registered.get("inode") != self.work.inode
            or self.work.read("memory.max") != str(3840 * MIB)
            or self.work.read("pids.max") != "480"
            or self.work.read("memory.swap.max") != "0"
            or self.work.read("cgroup.procs")
            or not {"memory", "pids"} <= set(self.work.read("cgroup.subtree_control").split())
        ):
            invalid("registered work branch mismatch")
        self.record["work_before"] = self.work.snapshot()
        save(
            self.output / "work-ack.json",
            {
                "name": self.work_name,
                "inode": self.work.inode,
                "lifecycle_inode": self.inode,
            },
        )

    def watch(self) -> None:
        assert self.child is not None and self.control is not None
        watched = os.pidfd_open(self.child.pid)
        try:
            while not select.select([watched], [], [], 0.02)[0]:
                if (
                    self.mode == "host"
                    and self.work is None
                    and (self.output / "work-registration.json").is_file()
                ):
                    self.register_work()
                if time.monotonic_ns() >= self.deadline - RESERVE:
                    self.record["stop_reason"] = "deadline"
                    break
            else:
                self.record["stop_reason"] = "controller-exit"
            self.begin_cleanup("controller-stop")
        finally:
            os.close(watched)
        self.record["controller_before_cleanup"] = self.control.snapshot()
        self.record["work_before_cleanup"] = self.work.snapshot() if self.work is not None else None
        if self.work is None:
            invalid("work branch was not registered")

    def begin_cleanup(self, reason: str) -> None:
        if self.cleanup_deadline_ns is not None:
            return
        anchor = time.monotonic_ns()
        self.cleanup_deadline_ns = min(self.deadline, anchor + RESERVE)
        self.record.update(
            cleanup_anchor_kind=reason,
            cleanup_anchor_ns=anchor,
            cleanup_deadline_ns=self.cleanup_deadline_ns,
        )

    def publish_closing(self) -> bool:
        assert self.cleanup_deadline_ns is not None
        while True:
            if time.monotonic_ns() >= self.cleanup_deadline_ns:
                expired("lifecycle closing lock deadline")
            try:
                fcntl.flock(self.guardian_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(0.005)
        try:
            if time.monotonic_ns() >= self.cleanup_deadline_ns:
                expired("lifecycle closing lock deadline")
            save(
                self.output / "closing.json",
                {"closing_ns": time.monotonic_ns(), "lifecycle_inode": self.inode},
            )
        finally:
            fcntl.flock(self.guardian_lock, fcntl.LOCK_UN)
        return True

    def note_error(self, label: str, error: BaseException) -> None:
        self.cleanup_errors.append(f"{label}: {type(error).__name__}: {error}")

    def clean_group(self, label: str, group: Group | None) -> None:
        if group is None:
            return
        try:
            self.record[f"{label}_kill_seconds"] = group.kill()
        except BaseException as error:
            logging.exception("guardian group kill failed")
            self.note_error(label, error)
        try:
            self.record[f"{label}_after_kill"] = group.snapshot()
        except BaseException as error:
            logging.exception("guardian group snapshot failed")
            self.note_error(label, error)
        try:
            group.remove()
            self.record[f"{label}_absent_observed_ns"] = time.monotonic_ns()
        except BaseException as error:
            logging.exception("guardian group removal failed")
            self.note_error(label, error)

    def cleanup_groups(self, closing_published: bool) -> None:
        assert self.cleanup_deadline_ns is not None
        if (
            self.work is None
            and self.work_name is not None
            and (self.root.path / self.work_name).exists()
        ):
            try:
                self.work = self.root.adopt(self.work_name)
            except BaseException as error:
                logging.exception("guardian work adoption failed")
                self.note_error("adopt work", error)
        order = (
            (("work", self.work), ("control", self.control))
            if closing_published
            else (("control", self.control), ("work", self.work))
        )
        for label, group in order:
            self.clean_group(label, group)
        if self.child is not None:
            try:
                if self.child.poll() is None:
                    self.child.kill()
                self.record["controller_native_status"] = self.child.wait(
                    timeout=max(
                        0.001,
                        min(1.0, (self.cleanup_deadline_ns - time.monotonic_ns()) / 1e9),
                    )
                )
            except BaseException as error:
                logging.exception("guardian controller wait failed")
                self.note_error("controller wait", error)

    def cleanup(self) -> None:
        self.begin_cleanup("cleanup-start")
        assert self.cleanup_deadline_ns is not None
        self.record["cleanup_started_ns"] = time.monotonic_ns()
        closing_published = False
        try:
            closing_published = self.publish_closing()
        except BaseException as error:
            logging.exception("guardian closing publication failed")
            self.note_error("closing", error)
        self.record["closing_published"] = closing_published
        self.cleanup_groups(closing_published)
        self.record.update(
            cleanup_errors=self.cleanup_errors, error=self.error, finished_ns=time.monotonic_ns()
        )
        self.record["success"] = (
            self.error is None
            and not self.cleanup_errors
            and self.record.get("controller_native_status") == 0
            and self.record.get("stop_reason") == "controller-exit"
            and time.monotonic_ns() < self.cleanup_deadline_ns
        )
        try:
            save(self.output / "guardian.json", self.record)
            if time.monotonic_ns() >= self.cleanup_deadline_ns:
                self.record["success"] = False
                self.record["persistence_exceeded_deadline"] = True
                save(self.output / "guardian.json", self.record)
        except BaseException:
            logging.exception("guardian result persistence failed")
            self.record["success"] = False
        finally:
            if self.guard is not None:
                os.close(self.guard.fd)
            os.close(self.root.fd)
            os.close(self.controller_lock)
            os.close(self.guardian_lock)

    def status(self) -> int:
        status = self.record.get("controller_native_status")
        if self.record["success"]:
            return 0
        if (
            isinstance(status, int)
            and status != 0
            and not self.cleanup_errors
            and self.error is None
            and self.record.get("stop_reason") == "controller-exit"
        ):
            return status if status > 0 else 128 - status
        return 1


def _locks(output: Path) -> tuple[int, int, int]:
    lock_path = output / "lifecycle.lock"
    guardian = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        controller = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
    except BaseException:
        os.close(guardian)
        raise
    info = os.fstat(guardian)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or os.fstat(controller).st_ino != info.st_ino
    ):
        os.close(guardian)
        os.close(controller)
        invalid("invalid lifecycle lock")
    return guardian, controller, info.st_ino


def provider(mode: str, output: Path, deadline: int, unit: str, argv: list[str]) -> int:
    """Own only the current verified unit, and reap its work and control leaves."""
    if (
        os.getuid() == 0
        or not output.is_absolute()
        or not argv
        or not re.fullmatch(r"quality-rl00bc-[a-f0-9]{32}\.service", unit)
    ):
        invalid("unprivileged provider, absolute output and coordinator required")
    if time.monotonic_ns() >= deadline - RESERVE:
        invalid("insufficient original deadline")
    output.mkdir(parents=True, exist_ok=True)
    guardian_lock, controller_lock, inode = _locks(output)
    try:
        root = Group.current()
    except BaseException:
        os.close(guardian_lock)
        os.close(controller_lock)
        raise
    locks = (guardian_lock, controller_lock, inode)
    guardian = _Guardian(mode, output, deadline, unit, argv, root, *locks)
    guardian.record.update(
        {
            "mode": mode,
            "deadline_ns": deadline,
            "success": False,
            "backstop_required": "external systemd control-group stop",
            "lifecycle_inode": inode,
        }
    )
    try:
        guardian.prepare()
        guardian.start_controller()
        guardian.watch()
    except BaseException as error:
        logging.exception("guardian execution failed")
        guardian.error = f"{type(error).__name__}: {error}"
    finally:
        guardian.cleanup()
    return guardian.status()


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
