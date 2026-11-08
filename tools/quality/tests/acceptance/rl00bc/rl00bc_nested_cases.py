"""Real nested requests, shared-time observations, and bounded failure oracles."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import CGROUP, Group
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_nested_process import (
    Worker,
    live,
    native,
    require_success,
    wait_until,
)
from tests.acceptance.rl00bc.rl00bc_nested_protocol import Parent, Protocol
from tests.acceptance.rl00bc.rl00bc_nested_scope import (
    DOMAIN_MEMORY, DOMAIN_TASKS, MIB, PARENT_MEMORY, PARENT_TASKS, POOL_MEMORY, POOL_TASKS,
)


def _check_limits(group: Group, memory: int, tasks: int) -> None:
    if (group.read("memory.max") != str(memory * MIB) or group.read("pids.max") != str(tasks)
            or group.read("memory.swap.max") != "0"):
        invalid("nested group limits differ from the preassigned budget")


def _leaf(parent: Group, identity: dict[str, object]) -> Group:
    name = Path(str(identity["cgroup"])).name
    return parent.adopt(name)


def _snapshot(parent: Parent, child: dict[str, object]) -> dict[str, object]:
    domain, pool = parent.domain.group, parent.pool()
    parent_leaf = _leaf(domain, parent.identity)
    try:
        child_leaf = _leaf(pool, child)
        try:
            _check_limits(domain, DOMAIN_MEMORY, DOMAIN_TASKS)
            _check_limits(parent_leaf, PARENT_MEMORY, PARENT_TASKS)
            _check_limits(pool, POOL_MEMORY, POOL_TASKS)
            _check_limits(child_leaf, 64, 8)
            if (PARENT_MEMORY + POOL_MEMORY > DOMAIN_MEMORY
                    or PARENT_TASKS + POOL_TASKS > DOMAIN_TASKS):
                invalid("nested parent and pool shares exceed their enclosing domain")
            return {
                "domain": domain.snapshot(), "parent_leaf": parent_leaf.snapshot(),
                "pool": pool.snapshot(), "child_leaf": child_leaf.snapshot(),
            }
        finally:
            os.close(child_leaf.fd)
    finally:
        os.close(parent_leaf.fd)


def match_result(identity: dict[str, object], result: dict[str, object]) -> None:
    """Bind the native marker to the kernel's descriptor-owned leaf."""
    before = result.get("before")
    if not isinstance(before, dict):
        invalid("nested kernel observation lacks leaf identity")
    path = cast(dict[str, object], before).get("path")
    if not isinstance(path, str):
        invalid("nested kernel leaf path is unavailable")
    if identity.get("cgroup") != "/" + str(Path(path).relative_to(CGROUP)):
        invalid("nested native identity differs from its kernel observation")


def _children(
    protocol: Protocol, index: int, deadline: int, claims: dict[str, dict[str, int]],
) -> tuple[list[Worker], list[dict[str, object]], list[int]]:
    workers = [
        protocol.child(parent, index, 64, 8, deadline,
                       claims[parent.domain.name]["requested_deadline_ns"])
        for parent in protocol.parents
    ]
    identities: list[dict[str, object]] = []
    pidfds: list[int] = []
    try:
        for parent in protocol.parents:
            marker = parent.mailbox / f"child-{index}.json"
            wait_until(marker.is_file, protocol.until())
            identity, pidfd = native(marker, parent.pool(), parent.domain.name)
            identities.append(identity)
            pidfds.append(pidfd)
        protocol.assert_parents_live()
        for identity, pidfd in zip(identities, pidfds, strict=True):
            live(identity, pidfd)
    except BaseException:
        for pidfd in pidfds:
            os.close(pidfd)
        raise
    return workers, identities, pidfds


def _snapshots(protocol: Protocol, identities: list[dict[str, object]]) -> list[dict[str, object]]:
    if protocol.parents[0].pool().inode == protocol.parents[1].pool().inode:
        invalid("nested parents share a child pool")
    return [_snapshot(parent, identity)
            for parent, identity in zip(protocol.parents, identities, strict=True)]


def _require_empty_pool(parent: Parent) -> None:
    with os.scandir(parent.pool().fd) as entries:
        if any(entry.is_dir(follow_symlinks=False) for entry in entries):
            invalid("rejected nested request left a child reservation")


def ordinary(protocol: Protocol, index: int, kind: str) -> dict[str, object]:
    """Observe two concurrent children while both actual native parents remain live."""
    claims = protocol.requests(index, kind, 64, 8)
    workers, identities, pidfds = _children(protocol, index, protocol.parent_stop, claims)
    try:
        snapshots = _snapshots(protocol, identities)
        protocol.assert_parents_live()
        for identity, pidfd in zip(identities, pidfds, strict=True):
            live(identity, pidfd)
        for parent in protocol.parents:
            (parent.mailbox / f"release-{index}.json").touch()
        results = [worker.wait(protocol.until()) for worker in workers]
        for identity, result in zip(identities, results, strict=True):
            require_success(result)
            match_result(identity, result)
        protocol.assert_parents_live()
        protocol.respond(index, kind)
        return {"children": identities, "deadline_claims": claims,
                "concurrent_snapshots": snapshots, "results": results}
    finally:
        for pidfd in pidfds:
            os.close(pidfd)


def reject(protocol: Protocol, index: int, kind: str, memory: int, tasks: int) -> dict[str, object]:
    """Demand immediate rejection of a request that only fits outside its own pool."""
    claims = protocol.requests(index, kind, memory, tasks)
    started = time.monotonic_ns()
    workers = [
        protocol.child(parent, index, memory, tasks,
                       claims[parent.domain.name]["clamped_deadline_ns"],
                       claims[parent.domain.name]["requested_deadline_ns"])
        for parent in protocol.parents
    ]
    deadline = min(protocol.until(), started + 3_000_000_000)
    results = [worker.wait(deadline) for worker in workers]
    finished = time.monotonic_ns()
    if finished > deadline:
        invalid("impossible nested request was not rejected promptly")
    for parent, result in zip(protocol.parents, results, strict=True):
        if result.get("success") is not False or "insufficient checker capacity" not in str(
            result.get("observation_error")
        ):
            invalid("impossible nested request was not rejected by its own pool")
        if (parent.mailbox / f"child-{index}.json").exists():
            invalid("rejected nested request ran a native child")
        _require_empty_pool(parent)
    protocol.assert_parents_live()
    protocol.respond(index, kind)
    return {"requested_ns": started, "rejected_observed_ns": finished,
            "deadline_claims": claims, "results": results}


def cancel(protocol: Protocol) -> dict[str, object]:
    """Interrupt actual child controllers while both native parents remain alive."""
    index, kind = 3, "cancel"
    claims = protocol.requests(index, kind, 64, 8)
    workers, identities, pidfds = _children(protocol, index, protocol.parent_stop, claims)
    try:
        snapshots = _snapshots(protocol, identities)
        protocol.assert_parents_live()
        for worker in workers:
            worker.cancel()
        results = [worker.wait(protocol.until()) for worker in workers]
        for result in results:
            if (result.get("success") is not False or result.get("cleanup_complete") is not True
                    or "KeyboardInterrupt" not in str(result.get("observation_error"))):
                invalid("nested cancellation did not preserve failure and clean up")
        protocol.assert_parents_live()
        protocol.respond(index, kind)
        return {"children": identities, "deadline_claims": claims,
                "concurrent_snapshots": snapshots, "results": results}
    finally:
        for pidfd in pidfds:
            os.close(pidfd)


def deadline(protocol: Protocol) -> dict[str, object]:
    """Request a later child deadline and observe the fixed earlier cutoff."""
    index, kind = 5, "deadline"
    claims = protocol.requests(index, kind, 64, 8)
    bounds = [claim["clamped_deadline_ns"] for claim in claims.values()]
    bound = min([*bounds, time.monotonic_ns() + 8_000_000_000])
    if bound - time.monotonic_ns() < 6_000_000_000:
        invalid("insufficient inherited deadline for nested deadline proof")
    workers, identities, pidfds = _children(protocol, index, bound, claims)
    try:
        snapshots = _snapshots(protocol, identities)
        results = [worker.wait(bound) for worker in workers]
        completed = time.monotonic_ns()
        for identity, result in zip(identities, results, strict=True):
            removed = result.get("removal_observed_ns")
            if (
                result.get("cause") != "timeout"
                or result.get("cleanup_complete") is not True
                or not isinstance(removed, int)
                or isinstance(removed, bool)
                or removed > bound
            ):
                invalid("nested child exceeded or reset its inherited deadline")
            match_result(identity, result)
        if completed > bound:
            invalid("nested child cleanup was observed after its fixed deadline")
        protocol.assert_parents_live()
        protocol.respond(index, kind)
        return {
            "parent_stop_ns": protocol.parent_stop, "child_deadline_ns": bound,
            "deadline_claims": claims,
            "completed_observed_ns": completed, "children": identities,
            "concurrent_snapshots": snapshots, "results": results,
        }
    finally:
        for pidfd in pidfds:
            os.close(pidfd)
