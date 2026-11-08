"""Create and clean two independently budgeted nested proof domains."""

from __future__ import annotations

import fcntl
import os
import stat
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc.rl00bc_errors import expired, invalid, unavailable
from tests.acceptance.rl00bc.rl00bc_kernel import lock_lifecycle

MIB = 1024 * 1024
DOMAIN_MEMORY, DOMAIN_TASKS = 512, 64
PARENT_MEMORY, PARENT_TASKS = 128, 8
POOL_MEMORY, POOL_TASKS = 320, 40


@dataclass
class Domain:
    """One parent scope and its separately delegated child pool."""

    name: str
    group: Group
    pool: Group | None = None


@dataclass
class Scope:
    """Only groups created under the inherited work descriptor are owned."""

    work: Group
    deadline: int
    domains: list[Domain] = field(default_factory=list[Domain])
    work_limits: tuple[str, str, str] | None = None
    removed_ns: dict[str, int] = field(default_factory=dict[str, int])

    def lock(self) -> tuple[int, Path]:
        inherited = int(os.environ["RL00_LIFECYCLE_FD"])
        closing = Path(os.environ["RL00_LIFECYCLE_CLOSING"])
        info = os.fstat(inherited)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_ino != int(os.environ["RL00_LIFECYCLE_INODE"])
                or not closing.is_absolute()):
            invalid("invalid nested proof lifecycle authority")
        fd = os.open(f"/proc/self/fd/{inherited}", os.O_RDWR | os.O_CLOEXEC)
        try:
            reopened = os.fstat(fd)
            if (reopened.st_dev, reopened.st_ino) != (info.st_dev, info.st_ino):
                invalid("nested proof lifecycle descriptor changed")
            lock_lifecycle(fd, self.deadline)
        except BaseException:
            os.close(fd)
            raise
        return fd, closing

    def allocate(self) -> None:
        fd, closing = self.lock()
        try:
            self._before_setup(closing)
            self._validate_work()
            for name in ("a", "b"):
                self._before_setup(closing)
                group = self.work.bare(uuid.uuid4().hex)
                domain = Domain(name, group)
                self.domains.append(domain)
                self._before_setup(closing)
                group.limit(DOMAIN_MEMORY, DOMAIN_TASKS)
                self._before_setup(closing)
                group.enable()
                self._before_setup(closing)
                domain.pool = group.bare(uuid.uuid4().hex)
                self._before_setup(closing)
                domain.pool.limit(POOL_MEMORY, POOL_TASKS)
                self._before_setup(closing)
                domain.pool.enable()
            self._before_setup(closing)
            self._validate_work_limits()
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _before_setup(self, closing: Path) -> None:
        if time.monotonic_ns() >= self.deadline:
            expired("nested proof setup deadline")
        if closing.exists():
            unavailable("guardian is closing the nested proof session")

    def _validate_work(self) -> None:
        self._identity(self.work)
        if self.work.read("cgroup.procs") or not {"memory", "pids"} <= set(
            self.work.read("cgroup.subtree_control").split()
        ):
            invalid("nested proof work branch is not empty and delegated")
        with os.scandir(self.work.fd) as entries:
            if any(entry.is_symlink() or entry.is_dir(follow_symlinks=False) for entry in entries):
                invalid("nested proof requires an idle owned work branch")
        self._validate_work_limits()
        self.work_limits = self._limits()

    def _validate_work_limits(self) -> None:
        limits = self._limits()
        if (int(limits[0]) < 2 * DOMAIN_MEMORY * MIB
                or int(limits[1]) < 2 * DOMAIN_TASKS or limits[2] != "0"):
            invalid("insufficient enclosing capacity for both nested domains")
        if self.work_limits is not None and limits != self.work_limits:
            invalid("nested proof enclosing limits changed")

    def _limits(self) -> tuple[str, str, str]:
        return (self.work.read("memory.max"), self.work.read("pids.max"),
                self.work.read("memory.swap.max"))

    @staticmethod
    def _identity(group: Group) -> None:
        descriptor = os.fstat(group.fd)
        path = group.path.stat()
        if ((descriptor.st_dev, descriptor.st_ino) != (path.st_dev, path.st_ino)
                or descriptor.st_ino != group.inode):
            invalid("nested proof group identity changed")

    @staticmethod
    def _group_limits(group: Group, memory: int, tasks: int) -> None:
        if (group.read("memory.max") != str(memory * MIB)
                or group.read("pids.max") != str(tasks)
                or group.read("memory.swap.max") != "0"):
            invalid("nested proof group limits changed")

    def validate(self) -> None:
        """Sample previously created ownership and exact preassigned limits."""
        self._identity(self.work)
        self._validate_work_limits()
        for domain in self.domains:
            group, pool = domain.group, domain.pool
            if (
                pool is None
                or group.path.parent != self.work.path
                or pool.path.parent != group.path
            ):
                invalid("nested proof group ancestry changed")
            self._identity(group)
            self._identity(pool)
            self._group_limits(group, DOMAIN_MEMORY, DOMAIN_TASKS)
            self._group_limits(pool, POOL_MEMORY, POOL_TASKS)

    def cleanup(self) -> list[str]:
        errors: list[str] = []
        try:
            fd, closing = self.lock()
        except (OSError, ValueError, RuntimeError) as error:
            errors.append(f"lifecycle lock: {type(error).__name__}: {error}")
            for domain in self.domains:
                self._close_domain(domain, errors)
            return errors
        try:
            if closing.exists():
                errors.append("guardian owns cleanup after closing")
                for domain in self.domains:
                    self._close_domain(domain, errors)
            else:
                for domain in self.domains:
                    self._remove(domain, errors)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        return errors

    def _remove(self, domain: Domain, errors: list[str]) -> None:
        if not self._cleanup_owned(domain, errors):
            self._close_domain(domain, errors)
            return
        try:
            domain.group.kill()
        except (OSError, ValueError, AssertionError) as error:
            errors.append(f"{domain.name} kill: {type(error).__name__}: {error}")
        if not self._cleanup_owned(domain, errors):
            self._close_domain(domain, errors)
            return
        if domain.pool is not None:
            self._close_fd(domain.pool.fd, domain.name, errors)
        try:
            domain.group.remove()
        except (OSError, ValueError, AssertionError) as error:
            errors.append(f"{domain.name} remove: {type(error).__name__}: {error}")
            self._close_fd(domain.group.fd, domain.name, errors)
            return
        try:
            found = os.open(
                domain.group.path.name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=self.work.fd,
            )
        except FileNotFoundError:
            observed = time.monotonic_ns()
            self.removed_ns[domain.name] = observed
            if observed > self.deadline:
                errors.append(f"{domain.name} absence observed after the original deadline")
        except OSError as error:
            errors.append(f"{domain.name} absence: {type(error).__name__}: {error}")
        else:
            self._close_fd(found, domain.name, errors)
            errors.append(f"{domain.name} path still exists after removal")

    def _cleanup_owned(self, domain: Domain, errors: list[str]) -> bool:
        try:
            self._identity(self.work)
            self._identity(domain.group)
            if domain.group.path.parent != self.work.path:
                invalid("nested cleanup domain ancestry changed")
            if domain.pool is not None:
                self._identity(domain.pool)
                if domain.pool.path.parent != domain.group.path:
                    invalid("nested cleanup pool ancestry changed")
        except (OSError, ValueError) as error:
            errors.append(f"{domain.name} ownership: {type(error).__name__}: {error}")
            return False
        return True

    @staticmethod
    def _close_fd(fd: int, label: str, errors: list[str]) -> None:
        try:
            os.close(fd)
        except OSError as error:
            errors.append(f"{label} descriptor: {type(error).__name__}: {error}")

    def _close_domain(self, domain: Domain, errors: list[str]) -> None:
        if domain.pool is not None:
            self._close_fd(domain.pool.fd, domain.name, errors)
        self._close_fd(domain.group.fd, domain.name, errors)
