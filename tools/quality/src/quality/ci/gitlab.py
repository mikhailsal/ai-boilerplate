"""Resolve the local GitLab wrapper's jobs for the shared gate lane contract."""

from __future__ import annotations

from collections.abc import Iterator

from quality.ci.lanes import GATE, LANES, check_lanes
from quality.ci.workflow import Table, finding, items, mapping
from quality.diagnostics import Diagnostic

PATHS = frozenset({".gitlab-ci.yml", "ci/gitlab/quality.gitlab-ci.yml"})
KEYWORDS = frozenset(
    {
        "after_script",
        "before_script",
        "cache",
        "default",
        "image",
        "include",
        "services",
        "spec",
        "stages",
        "types",
        "variables",
        "workflow",
    }
)


def _merge(base: Table, override: Table) -> dict[str, object]:
    merged = dict(base)
    for key, value in override.items():
        before, after = mapping(merged.get(key)), mapping(value)
        merged[key] = _merge(before, after) if before is not None and after is not None else value
    return merged


def _resolve(document: Table, name: str, chain: tuple[str, ...] = ()) -> Table | None:
    job = mapping(document.get(name))
    if job is None or name in chain:
        return None
    extends = job.get("extends", [])
    if not isinstance(extends, (str, list)):
        return None
    parents = [extends] if isinstance(extends, str) else items(job.get("extends"))
    merged: Table = {}
    for parent in parents:
        base = _resolve(document, str(parent), (*chain, name))
        if base is None:
            return None
        merged = _merge(merged, base)
    return _merge(merged, job)


def _script(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    for item in items(value):
        yield from _script(item)


def _required(job: Table) -> bool:
    return (
        job.get("allow_failure", False) is False
        and job.get("when", "on_success") in ("on_success", "always")
        and not any(key in job for key in ("rules", "only", "except"))
    )


def _jobs(document: Table) -> Iterator[tuple[str, Table | None]]:
    for name, value in document.items():
        job = mapping(value)
        if (
            name.startswith(".")
            or name in KEYWORDS
            or job is None
            or not {"script", "extends"}.intersection(job)
        ):
            continue
        yield name, _resolve(document, name)


def _has_gate(job: Table) -> bool:
    return any(GATE.search(text) for text in _script(job.get("script")))


def _hidden_gate(document: Table) -> bool:
    for name, value in document.items():
        job = mapping(value)
        if name.startswith(".") and job is not None and _has_gate(job):
            return True
    return False


def _lane_job(document: Table, job: Table) -> Table:
    variables = _merge(
        mapping(document.get("variables")) or {}, mapping(job.get("variables")) or {}
    )
    return {"env": variables, "steps": [{"run": text} for text in _script(job.get("script"))]}


def check_gitlab_lanes(path: str, document: Table) -> Iterator[Diagnostic]:
    """Check runnable local jobs, resolving extends and job-over-global variables."""
    gate_jobs: list[Table] = []
    for name, resolved in _jobs(document):
        if resolved is None:
            message = f"job '{name}' has an unresolved or cyclic extends chain"
            yield finding(LANES, path, message, name)
        elif _has_gate(resolved):
            gate_jobs.append(resolved)
    required = [_lane_job(document, job) for job in gate_jobs if _required(job)]
    if not required and (gate_jobs or _hidden_gate(document)):
        message = "the GitLab wrapper defines the gate but no required job runs it"
        yield finding(LANES, path, message, "gate")
    yield from check_lanes(path, required)
