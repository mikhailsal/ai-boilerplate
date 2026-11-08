"""Unrun, bounded native RL00b correctness comparisons and explicit proof gaps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, TypedDict, Unpack, cast

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import (
    rl00bc_comparison_oracle,
    rl00bc_corpus,
    rl00bc_phase_oracle,
    rl00bc_selection,
    rl00bc_trials,
    rl00bc_worker_oracle,
)
from tests.acceptance.rl00bc.rl00bc_errors import invalid, wrong_type

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


class TrialOptions(TypedDict, total=False):
    selected: str | None
    size: str
    mode: str
    target: str
    allocation_mib: int
    shared_mib: int
    workers: int
    coverage: bool
    instrument: bool
    justification: str | None


class TrialRunner(Protocol):
    def __call__(self, name: str, **options: Unpack[TrialOptions]) -> dict[str, object]: ...


def _selector_name(profile: str, target: str) -> tuple[str, str]:
    if profile in ("python", "php"):
        label = "allocation" if target == "native" else target
        if profile == "php" and label == "parameter-heavy":
            label = "parameterHeavy"
        return "variant", label
    label = {
        "native": "ordinary",
        "setup": "fixture",
        "teardown": "fixture",
        "slow": "ordinary",
        "justified": "ordinary",
        "retained": "ordinary",
    }.get(target, target)
    if profile == "dart":
        return "id", f"{label} case"
    if profile == "browser":
        return "id", f"parameter:{label}[desktop]"
    return "id", label


def _selector(profile: str, target: str, cases: list[dict[str, object]]) -> str:
    key, name = _selector_name(profile, target)
    matches = [case for case in cases if case.get(key) == name]
    if len(matches) != 1 or not isinstance(matches[0].get(key), str):
        invalid(f"native producer lacks unique selector for {target}")
    return cast(str, matches[0][key])


def _identities(cases: object) -> list[dict[str, object]]:
    if not isinstance(cases, list) or not cases:
        invalid("native baseline has no cases")
    result: list[dict[str, object]] = []
    for item in cast(list[object], cases):
        if not isinstance(item, dict):
            wrong_type("native result has no identity")
        case = cast(dict[str, object], item)
        if not isinstance(case.get("id"), str):
            wrong_type("native result has no identity")
        variant = case.get("variant", "default")
        if not isinstance(variant, str) or not variant:
            invalid("native result has no variant")
        result.append({"id": case["id"], "variant": variant})
    if len({cast(str, item["id"]) for item in result}) != len(result):
        invalid("duplicate native identities")
    return result


def _retained_phases(run: dict[str, object]) -> set[str]:
    """Read fixture-emitted shared setup boundaries, without attributing RSS to a case."""
    directory = run.get("events")
    if not isinstance(directory, str) or not Path(directory).is_dir():
        return set()
    phases: set[str] = set()
    for path in Path(directory).glob("*.json"):
        try:
            value: object = json.loads(path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            continue
        if isinstance(value, dict):
            event = cast(dict[str, object], value)
            if event.get("label", event.get("case")) != "retained":
                continue
            phase = event.get("phase")
            if isinstance(phase, str):
                phases.add(phase)
    return phases


def _check_retained(
    profile: str, canonical: dict[str, object], strict: dict[str, object], mismatches: list[str]
) -> None:
    start, end = {
        "python": ("session-setup-start", "session-setup"),
        "php": ("class-setup-start", "class-setup-end"),
        "node": ("retained-allocation-start", "retained-allocation-end"),
        "browser": ("retained-allocation-start", "retained-allocation-end"),
        "dart": ("retained-allocation-start", "retained-allocation-end"),
    }[profile]
    kernel = strict.get("kernel")
    if (
        not isinstance(kernel, dict)
        or cast(dict[str, object], kernel).get("resource_violation") != "own-memory"
    ):
        mismatches.append("retained strict did not hit its own memory boundary")
    if start not in _retained_phases(strict) or not {start, end} <= _retained_phases(canonical):
        mismatches.append("retained shared setup boundaries missing")


def _native_target(profile: str, target: str) -> str:
    if target == "native" and profile in ("python", "php"):
        return "allocation"
    if profile == "php" and target == "parameter-heavy":
        return "parameterHeavy"
    return target


def _target_options(profile: str, target: str) -> TrialOptions:
    return {
        "size": "large",
        "mode": "correctness",
        "target": _native_target(profile, target),
        "allocation_mib": rl00bc_trials.STRICT[profile][0],
        "shared_mib": 64,
        "coverage": profile != "browser",
        "instrument": True,
    }


def _justified(run: TrialRunner, profile: str, row: dict[str, object],
               canonical: dict[str, object], options: TrialOptions,
               mismatches: list[str], oracles: dict[str, object]) -> None:
    justified_opts: TrialOptions = {**options, "justification": "preregistered justified workload"}
    justified = run("justified-allowance", **justified_opts)
    oracles["justified-allowance"] = rl00bc_phase_oracle.evaluate(
        profile, "justified", cast(str, row["id"]), cast(str, row.get("variant", "default")),
        canonical, justified,
    )
    if justified.get("classification") != "observed-success":
        mismatches.append("justified allowance nonpass")


def _target(
    run: TrialRunner,
    profile: str,
    target: str,
    cases: list[dict[str, object]],
    mismatches: list[str],
    oracles: dict[str, object],
) -> None:
    try:
        selected_case = _selector(profile, target, cases)
    except ValueError as error:
        mismatches.append(str(error))
        oracles[target] = {"case_attribution": "unproved", "gaps": [str(error)]}
        return
    opts = _target_options(profile, target)
    canonical = run(f"{target}-canonical", **opts)
    strict_opts: TrialOptions = {**opts, "selected": selected_case, "coverage": False}
    strict = run(f"{target}-strict", **strict_opts)
    key, _ = _selector_name(profile, target)
    selected_row = next(case for case in cases if case.get(key) == selected_case)
    oracle = rl00bc_phase_oracle.evaluate(
        profile,
        target,
        cast(str, selected_row["id"]),
        cast(str, selected_row.get("variant", "default")),
        canonical,
        strict,
    )
    oracles[target] = oracle
    if canonical.get("classification") != "observed-success":
        mismatches.append(f"{target} canonical nonpass")
    expected = "deadline-exceeded" if target == "slow" else "own-boundary-resource-violation"
    if strict.get("classification") != expected:
        mismatches.append(f"{target} strict expected {expected}")
    if not rl00bc_comparison_oracle.matches(
        oracle, memory=target != "slow", shared=target == "retained"
    ):
        mismatches.append(f"{target} selected identity or phase scope unproved")
    if target == "retained":
        _check_retained(profile, canonical, strict, mismatches)
    if target == "justified":
        _justified(run, profile, selected_row, canonical, strict_opts, mismatches, oracles)


def _parallel(
    run: TrialRunner,
    profile: str,
    discovered: list[dict[str, object]],
    coverage: bool,
    mismatches: list[str],
) -> dict[str, object]:
    parallel = run(
        "baseline-large-workers2",
        size="large",
        mode="performance",
        workers=2,
        coverage=coverage,
        instrument=True,
    )
    try:
        parallel_ids = {
            (case["id"], case["variant"]) for case in _identities(parallel.get("native_cases"))
        }
        expected_ids = {(case["id"], case["variant"]) for case in discovered}
        if parallel.get("classification") != "observed-success" or parallel_ids != expected_ids:
            mismatches.append("two-worker identity parity unavailable")
    except ValueError, TypeError:
        mismatches.append("two-worker native identity unavailable")
    oracle = rl00bc_worker_oracle.evaluate(profile, parallel)
    if oracle.get("status") != "observed-overlap":
        mismatches.append("two-worker native overlap unproved")
    return oracle


def _scopes(
    profile: str,
    large: dict[str, object],
    small: dict[str, object],
    context: dict[str, str],
    mismatches: list[str],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    try:
        rl00bc_corpus.verify(profile, "large", large["native_cases"])
        rl00bc_corpus.verify(profile, "small", small["native_cases"])
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
    except (KeyError, ValueError, TypeError) as error:
        mismatches.append("native discovery or selection failed")
        return [], {"error": str(error)}
    else:
        return discovered, {"first_adoption": first, "unknown": unknown}


def _baselines(
    run: TrialRunner, coverage: bool, runs: dict[str, object], mismatches: list[str]
) -> tuple[dict[str, object], dict[str, object]]:
    for size in ("small", "large"):
        baseline = run(
            f"baseline-{size}", size=size, mode="performance", coverage=coverage, instrument=True
        )
        if baseline.get("classification") != "observed-success":
            mismatches.append(f"baseline-{size} nonpass")
    large = cast(dict[str, object], runs["baseline-large"])
    small = cast(dict[str, object], runs["baseline-small"])
    return large, small


def _collect(
    run: TrialRunner, profile: str, context: dict[str, str], runs: dict[str, object]
) -> dict[str, object]:
    coverage = profile != "browser"
    pending = [
        "real-git-candidate-mutations",
        "canonical-quality-coverage-and-scenario-reconciliation",
        "worker-attribution",
        "nested-capacity",
        "order-perturbation",
        "target-phase-attribution",
        "owned-child-membership",
    ]
    mismatches: list[str] = []
    oracles: dict[str, object] = {
        target: {"case_attribution": "unproved", "gaps": ["target trial not run"]}
        for target in TARGETS
    }
    large, small = _baselines(run, coverage, runs, mismatches)
    discovered, scopes = _scopes(profile, large, small, context, mismatches)
    cases = cast(list[dict[str, object]], large.get("native_cases", []))
    worker_oracle: dict[str, object] = {"status": "unproved", "error": "worker trial not run"}
    if discovered:
        for target in TARGETS:
            _target(run, profile, target, cases, mismatches, oracles)
        if profile != "php":
            worker_oracle = _parallel(run, profile, discovered, coverage, mismatches)
        else:
            pending.append("php-native-parallel-not-supported")
    return {
        "profile": profile,
        "runs": runs,
        "scopes": scopes,
        "mismatches": mismatches,
        "target_phase_oracles": oracles,
        "worker_oracle": worker_oracle,
        "required_proofs_pending": pending,
        "verdict": "comparisons-failed"
        if mismatches
        else "comparisons-passed-external-proofs-pending",
        "worker_instrumentation": (
            "event boundaries and kernel lifetime totals only; no case-memory attribution"
        ),
        "case_aliases": (
            "node/dart/browser workload targets may share native case identity; "
            "target is an experimental execution variant"
        ),
        "selection_limit": "synthetic changes only; actual Git candidate mutation proof pending",
    }


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
        invalid("unknown profile")
    context = {key: environment.get(f"RL00_CONTEXT_{key.upper()}", "") for key in CONTEXT_KEYS}
    if any(not value for value in context.values()):
        invalid("missing caller-bound candidate/base/tree/policy/runtime/source hashes")
    native_env = {
        key: value for key, value in environment.items() if not key.startswith("RL00_CONTEXT_")
    }
    native_env["RL00_SLOW_SECONDS"] = "20" if profile == "browser" else "8"
    output.mkdir(parents=True, exist_ok=False)
    runs: dict[str, object] = {}

    def run(name: str, **options: Unpack[TrialOptions]) -> dict[str, object]:
        observation = rl00bc_trials.one(
            work,
            repo,
            scratch,
            output / name,
            profile,
            native_env,
            ancestor_deadline_ns=ancestor_deadline_ns,
            **options,
        )
        runs[name] = observation
        return observation

    result = _collect(run, profile, context, runs)
    data = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > 1_048_576:
        invalid("correctness record exceeds finite size")
    (output / "correctness.json").write_bytes(data)
    return result
