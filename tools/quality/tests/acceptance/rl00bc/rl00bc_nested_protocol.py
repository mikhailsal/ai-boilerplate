"""Mailbox authority and process identity for nested-capacity proof cases."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, load, save
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_nested_process import Worker, launch, live, native, wait_until
from tests.acceptance.rl00bc.rl00bc_nested_scope import (
    PARENT_MEMORY,
    PARENT_TASKS,
    POOL_MEMORY,
    POOL_TASKS,
    Domain,
    Scope,
)


@dataclass
class Parent:
    """One live native parent and its independent assigned pool."""

    domain: Domain
    mailbox: Path
    worker: Worker
    identity: dict[str, object]
    pidfd: int

    def pool(self) -> Group:
        if self.domain.pool is None:
            invalid("nested parent pool is unavailable")
        return self.domain.pool


@dataclass
class Protocol:
    """Own all proof controllers and preserve a single enclosing deadline."""

    scope: Scope
    repo: Path
    output: Path
    environment: dict[str, str]
    deadline: int
    parent_stop: int
    lock_dev: int
    lock_ino: int
    parents: list[Parent] = field(default_factory=list[Parent])
    workers: list[Worker] = field(default_factory=list[Worker])

    def until(self, seconds: int = 10) -> int:
        return min(self.parent_stop - 3_000_000_000, time.monotonic_ns() + seconds * 1_000_000_000)

    def lock_args(self) -> list[str]:
        return ["--lock-dev", str(self.lock_dev), "--lock-ino", str(self.lock_ino)]

    def start_parent(self, domain: Domain) -> None:
        mailbox = self.output / f"mailbox-{domain.name}"
        argv = [
            "parent", "--name", domain.name, "--deadline", str(self.parent_stop), *self.lock_args(),
            "--mailbox", str(mailbox), "--pool-memory", str(POOL_MEMORY),
            "--pool-tasks", str(POOL_TASKS),
        ]
        worker = launch(domain.group, self.repo, self.output / f"parent-{domain.name}",
                        self.environment, argv, memory=PARENT_MEMORY, tasks=PARENT_TASKS,
                        deadline=self.deadline, payload_deadline=self.parent_stop)
        self.workers.append(worker)
        wait_until((mailbox / "identity.json").is_file, self.until())
        identity, pidfd = native(mailbox / "identity.json", domain.group, domain.name)
        self.parents.append(Parent(domain, mailbox, worker, identity, pidfd))

    def assert_parents_live(self) -> None:
        if len(self.parents) != 2:
            invalid("both native parents must be present")
        self.scope.validate()
        for parent in self.parents:
            live(parent.identity, parent.pidfd)

    def requests(
        self, index: int, kind: str, memory: int, tasks: int,
    ) -> dict[str, dict[str, int]]:
        self.assert_parents_live()
        claims: dict[str, dict[str, int]] = {}
        for parent in self.parents:
            path = parent.mailbox / f"request-{index}.json"
            wait_until(path.is_file, self.until())
            request = load(path)
            if (
                request.get("parent") != parent.domain.name
                or request.get("pid") != parent.identity["pid"]
                or request.get("kind") != kind
                or request.get("memory_mib") != memory
                or request.get("tasks") != tasks
            ):
                invalid("nested mailbox request does not match its live parent and fixed plan")
            claims[parent.domain.name] = self._deadline_claim(kind, request)
        self.assert_parents_live()
        return claims

    def _deadline_claim(self, kind: str, request: dict[str, object]) -> dict[str, int]:
        requested = request.get("requested_deadline_ns")
        sent = request.get("requested_ns")
        if (isinstance(requested, bool) or not isinstance(requested, int)
                or isinstance(sent, bool) or not isinstance(sent, int)):
            invalid("nested parent deadline request is invalid")
        expected = self.parent_stop + 60_000_000_000 if kind == "deadline" else self.parent_stop
        if requested != expected or not 0 < sent <= time.monotonic_ns() or sent >= self.parent_stop:
            invalid("nested parent deadline request does not match the fixed plan")
        return {
            "request_observed_ns": sent,
            "requested_deadline_ns": requested,
            "trusted_parent_stop_ns": self.parent_stop,
            "clamped_deadline_ns": min(requested, self.parent_stop),
        }

    def child(
        self, parent: Parent, index: int, memory: int, tasks: int, deadline: int,
        requested_deadline: int,
    ) -> Worker:
        if deadline > min(requested_deadline, self.parent_stop):
            invalid("nested child deadline exceeds its parent request or trusted stop")
        marker = parent.mailbox / f"child-{index}.json"
        release = parent.mailbox / f"release-{index}.json"
        argv = ["child", "--name", parent.domain.name, "--deadline", str(self.parent_stop),
                *self.lock_args(), "--marker", str(marker), "--release", str(release)]
        worker = launch(
            parent.pool(), self.repo, self.output / f"child-{parent.domain.name}-{index}",
            self.environment, argv, memory=memory, tasks=tasks, deadline=deadline,
            payload_deadline=requested_deadline,
        )
        self.workers.append(worker)
        return worker

    def respond(self, index: int, kind: str) -> None:
        self.assert_parents_live()
        for parent in self.parents:
            save(parent.mailbox / f"response-{index}.json", {
                "accepted": True, "kind": kind, "observed_ns": time.monotonic_ns(),
            })
