"""Unrun, bounded native RL00b correctness comparisons and explicit proof gaps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_selection, rl00bc_trials

CONTEXT_KEYS = ("candidate", "base", "tested_tree", "policy", "runtime", "source")
TARGETS = (
    "native",
    "setup",
    "teardown",
    "child",
    "parameter-heavy",
    "slow",
    "justified",
    "retained",
)


def _selector(profile: str, target: str, cases: list[dict[str, object]]) -> str:
    if profile in ("python", "php"):
        label = "allocation" if target == "native" else target
        if profile == "php" and label == "parameter-heavy":
            label = "parameterHeavy"
        matches = [case for case in cases if case.get("variant") == label]
        key = "variant"
    else:
        label = {
            "native": "ordinary",
            "setup": "fixture",
            "teardown": "fixture",
            "slow": "ordinary",
            "justified": "ordinary",
            "retained": "ordinary",
        }.get(target, target)
        if profile == "dart":
            name = f"{label} case"
        elif profile == "browser":
            name = f"parameter:{label}[desktop]"
        else:
            name = label
        matches = [case for case in cases if case.get("id") == name]
        key = "id"
    if len(matches) != 1 or not isinstance(matches[0].get(key), str):
        raise ValueError(f"native producer lacks unique selector for {target}")
    return cast(str, matches[0][key])


def _identities(cases: object) -> list[dict[str, object]]:
    if not isinstance(cases, list) or not cases:
        raise ValueError("native baseline has no cases")
    result: list[dict[str, object]] = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise ValueError("native result has no identity")
        variant = case.get("variant", "default")
        if not isinstance(variant, str) or not variant:
            raise ValueError("native result has no variant")
        result.append({"id": case["id"], "variant": variant})
    if len({cast(str, item["id"]) for item in result}) != len(result):
        raise ValueError("duplicate native identities")
    return result


def _retained_phases(run: dict[str, object]) -> set[str]:
    """Read fixture-emitted shared setup boundaries, without attributing RSS to a case."""
    directory = run.get("events")
    if not isinstance(directory, str) or not Path(directory).is_dir():
        return set()
    phases: set[str] = set()
    for path in Path(directory).glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            continue
        if isinstance(value, dict) and value.get("label", value.get("case")) == "retained":
            phase = value.get("phase")
            if isinstance(phase, str):
                phases.add(phase)
    return phases


def check(
    work: Group,
    repo: Path,
    scratch: Path,
    output: Path,
    profile: str,
    environment: dict[str, str],
    *,
    ancestor_deadline_ns: int,
) -> dict[str, object]:
    """Run preregistered comparisons; no single observation certifies RL00b."""
    if profile not in rl00bc_trials.STRICT:
        raise ValueError("unknown profile")
    context = {key: environment.get(f"RL00_CONTEXT_{key.upper()}", "") for key in CONTEXT_KEYS}
    if any(not value for value in context.values()):
        raise ValueError("missing caller-bound candidate/base/tree/policy/runtime/source hashes")
    native_env = {
        key: value for key, value in environment.items() if not key.startswith("RL00_CONTEXT_")
    }
    native_env["RL00_SLOW_SECONDS"] = "20" if profile == "browser" else "8"
    output.mkdir(parents=True, exist_ok=False)
    coverage = profile != "browser"
    allocation = rl00bc_trials.STRICT[profile][0]
    runs: dict[str, object] = {}
    pending: list[str] = [
        "real-git-candidate-mutations",
        "canonical-quality-coverage-and-scenario-reconciliation",
        "worker-attribution",
        "nested-capacity",
        "order-perturbation",
    ]
    mismatches: list[str] = []

    def run(name: str, **options: object) -> dict[str, object]:
        observation = rl00bc_trials.one(
            work,
            repo,
            scratch,
            output / name,
            profile,
            native_env,
            ancestor_deadline_ns=ancestor_deadline_ns,
            **options,
        )  # type: ignore[arg-type]
        runs[name] = observation
        return observation

    for size in ("small", "large"):
        baseline = run(
            f"baseline-{size}", size=size, mode="performance", coverage=coverage, instrument=True
        )
        if baseline.get("classification") != "observed-success":
            mismatches.append(f"baseline-{size} nonpass")
    large = cast(dict[str, object], runs["baseline-large"])
    small = cast(dict[str, object], runs["baseline-small"])
    try:
        discovered = _identities(large["native_cases"])
        small_ids = {item["id"] for item in _identities(small["native_cases"])}
        if not small_ids <= {item["id"] for item in discovered}:
            mismatches.append("large corpus lost small identities")
        scope_context = cast(dict[str, object], dict(context))
        first = rl00bc_selection.build(scope_context, discovered, [], first_adoption=True)
        unknown = rl00bc_selection.build(
            scope_context, discovered, [{"kind": "unknown", "path": "unknown"}]
        )
        selected = {cast(str, item["id"]) for item in discovered}
        if (
            set(cast(list[str], first["selected"])) != selected
            or set(cast(list[str], unknown["selected"])) != selected
        ):
            mismatches.append("selection fallback incomplete")
        scopes: dict[str, object] = {"first_adoption": first, "unknown": unknown}
    except (KeyError, ValueError) as error:
        discovered = []
        scopes = {"error": str(error)}
        mismatches.append("native discovery or selection failed")

    cases = cast(list[dict[str, object]], large.get("native_cases", []))
    if discovered:
        for target in TARGETS:
            try:
                selected_case = _selector(profile, target, cases)
            except ValueError as error:
                mismatches.append(str(error))
                continue
            native_target = (
                "allocation" if target == "native" and profile in ("python", "php") else target
            )
            if profile == "php" and target == "parameter-heavy":
                native_target = "parameterHeavy"
            opts: dict[str, object] = {
                "size": "large",
                "mode": "correctness",
                "target": native_target,
                "allocation_mib": allocation,
                "shared_mib": 64,
                "coverage": coverage,
                "instrument": True,
            }
            canonical = run(f"{target}-canonical", **opts)
            strict_opts = {**opts, "selected": selected_case, "coverage": False}
            strict = run(f"{target}-strict", **strict_opts)
            if canonical.get("classification") != "observed-success":
                mismatches.append(f"{target} canonical nonpass")
            expected = (
                "deadline-exceeded" if target == "slow" else "own-boundary-resource-violation"
            )
            if strict.get("classification") != expected:
                mismatches.append(f"{target} strict expected {expected}")
            if target == "retained":
                start, end = {
                    "python": ("session-setup-start", "session-setup"),
                    "php": ("class-setup-start", "class-setup-end"),
                    "node": ("retained-allocation-start", "retained-allocation-end"),
                    "browser": ("retained-allocation-start", "retained-allocation-end"),
                    "dart": ("retained-allocation-start", "retained-allocation-end"),
                }[profile]
                kernel = strict.get("kernel")
                if not isinstance(kernel, dict) or kernel.get("resource_violation") != "own-memory":
                    mismatches.append("retained strict did not hit its own memory boundary")
                if start not in _retained_phases(strict) or not {start, end} <= _retained_phases(
                    canonical
                ):
                    mismatches.append("retained shared setup boundaries missing")
            if target == "justified":
                justified = run(
                    "justified-allowance",
                    **strict_opts,
                    justification="preregistered justified workload",
                )
                if justified.get("classification") != "observed-success":
                    mismatches.append("justified allowance nonpass")
        if profile != "php":
            parallel = run(
                "baseline-large-workers2",
                size="large",
                mode="performance",
                workers=2,
                coverage=coverage,
                instrument=True,
            )
            try:
                if parallel.get("classification") != "observed-success" or {
                    (case["id"], case["variant"])
                    for case in _identities(parallel.get("native_cases"))
                } != {(case["id"], case["variant"]) for case in discovered}:
                    mismatches.append("two-worker identity parity unavailable")
            except ValueError:
                mismatches.append("two-worker native identity unavailable")
        else:
            pending.append("php-native-parallel-not-supported")
    result: dict[str, object] = {
        "profile": profile,
        "runs": runs,
        "scopes": scopes,
        "mismatches": mismatches,
        "required_proofs_pending": pending,
        "verdict": "comparisons-failed"
        if mismatches
        else "comparisons-passed-external-proofs-pending",
        "worker_instrumentation": "event boundaries and kernel lifetime totals only; no case-memory attribution",
        "case_aliases": "node/dart/browser workload targets may share native case identity; target is an experimental execution variant",
        "selection_limit": "synthetic changes only; actual Git candidate mutation proof pending",
    }
    data = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > 1_048_576:
        raise ValueError("correctness record exceeds finite size")
    (output / "correctness.json").write_bytes(data)
    return result
