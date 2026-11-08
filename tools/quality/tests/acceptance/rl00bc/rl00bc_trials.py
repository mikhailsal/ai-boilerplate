"""One bounded native trial for the unrun RL00b/c research harness.

Provider materialization is controller-side and timed separately; every native
command, including the browser build, runs inside the same protected leaf.
This module neither provisions a leaf nor caches a resource verdict.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Protocol

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_dart, rl00bc_kernel, rl00bc_node, rl00bc_php, rl00bc_python

LIMIT = 65536
RESERVE_NS = 3_000_000_000
PATH_KEYS = frozenset({
    "RL00_PYTHON", "RL00_CHILD_PYTHON", "RL00_PHP", "RL00_PHPUNIT",
    "RL00_PHP_AUTOLOAD", "RL00_XDEBUG_LOADED", "RL00_NODE", "RL00_NODE_MODULES",
    "RL00_CHROMIUM", "RL00_DART", "RL00_DART_PACKAGE_CONFIG", "RL00_SLOW_SECONDS",
})


class Provider(Protocol):
    def prepare(self, root: Path, repo: Path, profile: str) -> None: ...

    def command(self, root: Path, repo: Path, output: Path, selected: str | None, *,
                profile: str, workers: int, coverage: bool) -> list[str]: ...

    def results(self, root: Path, output: Path, *, profile: str) -> list[dict[str, object]]: ...


PROVIDERS: dict[str, Provider] = {
    "python": rl00bc_python, "php": rl00bc_php, "node": rl00bc_node,
    "browser": rl00bc_node, "dart": rl00bc_dart,
}
STRICT: dict[str, tuple[int, int, float]] = {
    "python": (384, 128, 5.0), "php": (384, 128, 5.0),
    "node": (768, 128, 5.0), "dart": (1024, 128, 5.0),
    "browser": (1536, 256, 12.0),
}


def _save(path: Path, value: object) -> bytes:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > LIMIT:
        raise ValueError(f"bounded experiment record exceeds {LIMIT} bytes")
    path.write_bytes(data)
    return data


def _environment(environment: dict[str, str], root: Path, output: Path, *,
                 size: str, mode: str, target: str, allocation_mib: int,
                 shared_mib: int, instrument: bool, coverage: bool) -> dict[str, str]:
    unknown = set(environment) - PATH_KEYS
    if unknown:
        raise ValueError(f"unsupported environment keys: {sorted(unknown)}")
    if size not in {"small", "large"} or mode not in {"correctness", "performance"}:
        raise ValueError("invalid corpus configuration")
    if not 1 <= allocation_mib <= 1536 or not 0 <= shared_mib <= 128:
        raise ValueError("invalid finite allocation")
    if len(target) > 128 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in target):
        raise ValueError("invalid target label")
    if any(not isinstance(v, str) or len(v) > 4096 or "\0" in v for v in environment.values()):
        raise ValueError("invalid environment value")
    home = root / "home"
    temporary = root / "tmp"
    events = output / "events"
    for directory in (home, temporary, events):
        directory.mkdir(parents=True, exist_ok=True)
    tool_dirs: list[str] = []
    for key in ("RL00_NODE", "RL00_PYTHON"):
        if key in environment:
            executable = Path(environment[key])
            if not executable.is_absolute() or not executable.is_file():
                raise ValueError(f"{key} must name an absolute executable file")
            directory = str(executable.parent)
            if directory not in tool_dirs:
                tool_dirs.append(directory)
    search_path = ":".join([*tool_dirs, "/usr/local/bin", "/usr/bin", "/bin"])
    return {
        "PATH": search_path, "HOME": str(home), "TMPDIR": str(temporary),
        "XDG_CACHE_HOME": str(home / ".cache"), "CI": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "XDEBUG_MODE": "coverage" if coverage else "off", **environment,
        "RL00_MODE": mode, "RL00_SIZE": size, "RL00_TARGET": target,
        "RL00_ALLOC_MIB": str(allocation_mib), "RL00_SHARED_MIB": str(shared_mib),
        "RL00_INSTRUMENT": "1" if instrument else "0", "RL00_EVENT_DIR": str(events),
    }


def _provider_commands(provider: Provider, root: Path, repo: Path, output: Path,
                       profile: str, selected: str | None, workers: int,
                       coverage: bool, env: dict[str, str]) -> list[str]:
    # Providers read process environment; caller must serialize this preparation.
    keys = {key for key in os.environ if key.startswith("RL00_")} | {
        key for key in env if key.startswith("RL00_")
    }
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        os.environ.update({key: value for key, value in env.items() if key.startswith("RL00_")})
        provider.prepare(root, repo, profile)
        return provider.command(root, repo, output, selected, profile=profile,
                                workers=workers, coverage=coverage)
    finally:
        for key in keys:
            os.environ.pop(key, None)
        os.environ.update({key: value for key, value in previous.items() if value is not None})


def one(work: Group, repo: Path, scratch: Path, output: Path, profile: str,
        environment: dict[str, str], *, selected: str | None = None, size: str = "small",
        mode: str = "performance", target: str = "", allocation_mib: int = 1,
        shared_mib: int = 64, workers: int = 1, coverage: bool = True,
        instrument: bool = True, justification: str | None = None,
        ancestor_deadline_ns: int) -> dict[str, object]:
    """Run a fresh native subject under one leaf and persist separate evidence."""
    start_ns = time.monotonic_ns()
    if profile not in PROVIDERS or workers not in (1, 2):
        raise ValueError("unsupported profile or workers")
    if selected is not None and (not selected or len(selected) > 256 or "\0" in selected):
        raise ValueError("invalid selected identity")
    memory_mib, tasks, seconds = ((3072, 256, 90.0) if selected is None else STRICT[profile])
    budget_class = "canonical" if selected is None else "ordinary"
    if justification is not None:
        if (justification != "preregistered justified workload" or selected is None or
                mode != "correctness" or target != "justified" or memory_mib + 512 > 3072):
            raise ValueError("justified allowance is restricted to the preregistered selected workload")
        memory_mib += 512
        budget_class = "preregistered-justified"
    native_deadline_ns = min(start_ns + int(seconds * 1_000_000_000),
                             ancestor_deadline_ns - RESERVE_NS)
    repo, scratch, output = repo.absolute(), scratch.absolute(), output.absolute()
    scratch.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=False)
    root = scratch / f"rl00bc-{uuid.uuid4().hex}"
    env = _environment(environment, root, output, size=size, mode=mode, target=target,
                       allocation_mib=allocation_mib, shared_mib=shared_mib,
                       instrument=instrument, coverage=coverage)
    native_output = output / "native"
    provider = PROVIDERS[profile]
    argv = _provider_commands(provider, root, repo, native_output, profile, selected,
                              workers, coverage, env)
    commands = [argv]
    if profile == "browser":
        if coverage:
            raise ValueError("browser profile has no native unit coverage")
        commands.insert(0, [env["RL00_NODE"], str(Path(env["RL00_NODE_MODULES"]) / "vite/bin/vite.js"), "build", str(root)])
    if native_deadline_ns <= time.monotonic_ns():
        raise ValueError("ancestor deadline exhausted during preparation")
    plan = {"cwd": str(root), "commands": commands, "events": str(output / "events"),
            "deadline_ns": native_deadline_ns}
    plan_path = output / "native-plan.json"
    plan_hash = hashlib.sha256(_save(plan_path, plan)).hexdigest()
    preparation_seconds = (time.monotonic_ns() - start_ns) / 1_000_000_000
    wrapper = Path(__file__).with_name("rl00bc_native.py").absolute()
    raw = rl00bc_kernel.execute(work, [sys.executable, str(wrapper), str(plan_path)], root, env,
                                output / "kernel", memory_mib=memory_mib, tasks=tasks,
                                native_seconds=seconds, ancestor_deadline_ns=ancestor_deadline_ns,
                                payload_deadline_ns=native_deadline_ns)
    cases: list[dict[str, object]] = []
    parse_error: str | None = None
    try:
        cases = provider.results(root, native_output, profile=profile)
        if selected is not None:
            matches = [case for case in cases if selected in (case.get("id"), case.get("variant"))]
            if len(cases) != 1 or len(matches) != 1:
                raise ValueError("native selected identity missing or unexpected")
    except Exception as error:
        parse_error = f"{type(error).__name__}: {error}"[:1024]
        cases = []
    violation = raw.get("resource_violation")
    if violation in ("own-memory", "own-tasks"):
        classification = "own-boundary-resource-violation"
    elif violation == "ancestor-resource":
        classification = "ancestor-resource-violation-unknown-case"
    elif violation == "timeout":
        classification = "deadline-exceeded"
    elif violation is not None:
        classification = "unclassified-resource-nonpass"
    elif not raw.get("success") or not raw.get("cleanup_complete"):
        classification = "native-or-environment-nonpass"
    elif parse_error is not None:
        classification = "invalid-native-evidence"
    elif any(case.get("outcome") not in ("passed", "pass", "success", "expected") for case in cases):
        classification = "native-nonpass"
    else:
        classification = "observed-success"
    result: dict[str, object] = {
        "profile": profile, "selected": selected, "scope": "canonical-suite" if selected is None else "selected-case",
        "measurement_kind": "kernel-charged-leaf", "classification": classification,
        "strict_verification": "not-applicable" if selected is None else "experimental-evidence-only",
        "native_cases": cases, "parse_error": parse_error, "kernel": raw,
        "native_plan_sha256": plan_hash, "native_plan": str(plan_path),
        "preparation_seconds": preparation_seconds, "kernel_evidence": str(output / "kernel/result.json"),
        "events": str(output / "events"), "memory_limit_mib": memory_mib, "task_limit": tasks,
        "native_deadline_ns": native_deadline_ns, "ancestor_deadline_ns": ancestor_deadline_ns,
        "size": size, "mode": mode, "target": target, "workers": workers,
        "allocation_mib": allocation_mib, "shared_mib": shared_mib, "coverage": coverage,
        "budget_class": budget_class, "justification": justification,
    }
    _save(output / "trial.json", result)
    return result
