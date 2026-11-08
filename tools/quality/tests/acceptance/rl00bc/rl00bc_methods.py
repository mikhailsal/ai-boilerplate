"""Bounded three-method observations for a fixed RL00b/c corpus.

This experiment records evidence, not a per-case compliance certification.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import rl00bc_corpus, rl00bc_selection, rl00bc_trials
from tests.acceptance.rl00bc.rl00bc_errors import invalid

_KEYS = ("candidate", "base", "tested_tree", "policy", "runtime", "source")
_LABELS = ("ordinary", "excessive", "justified")


def _context(environment: dict[str, str]) -> dict[str, object]:
    context: dict[str, object] = {
        key: environment.get(f"RL00_CONTEXT_{key.upper()}", "") for key in _KEYS
    }
    if any(not value for value in context.values()):
        invalid("missing caller-bound candidate, tree, policy, runtime or source identity")
    return context


def _target(profile: str, label: str) -> str:
    if label == "ordinary":
        return ""
    if label == "justified":
        return "justified"
    return "allocation" if profile in ("python", "php") else "native"


def _target_case(profile: str, case: rl00bc_corpus.Case, label: str) -> bool:
    if label == "ordinary":
        return False
    if profile in ("python", "php"):
        return case.variant == ("allocation" if label == "excessive" else "justified")
    if profile == "browser":
        return case.identity.startswith("parameter:ordinary[")
    return case.identity == ("ordinary case" if profile == "dart" else "ordinary")


def _allowance(profile: str, label: str, case: rl00bc_corpus.Case | None) -> str | None:
    if case is not None and label == "justified" and _target_case(profile, case, label):
        return "preregistered justified workload"
    return None


@dataclass
class _Experiment:
    work: Group
    repo: Path
    scratch: Path
    output: Path
    profile: str
    environment: dict[str, str]
    deadline: int
    context: dict[str, object]
    summary: dict[str, object] = field(default_factory=dict[str, object])
    attempts: list[dict[str, object]] = field(default_factory=list[dict[str, object]])

    def persist(self) -> None:
        path = self.output / "methods.json"
        path.write_text(json.dumps(self.summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def trial(self, label: str, arm: str, case: rl00bc_corpus.Case | None) -> dict[str, object]:
        number = len(self.attempts)
        path = self.output / f"trial-{number:04d}"
        attempt: dict[str, object] = {
            "label": label,
            "arm": arm,
            "path": str(path),
            "selector": case.selector if case else None,
            "status": "in-progress",
        }
        self.attempts.append(attempt)
        self.persist()
        target = _target(self.profile, label)
        allowance = _allowance(self.profile, label, case)
        record = rl00bc_trials.one(
            self.work,
            self.repo,
            self.scratch,
            path,
            self.profile,
            self.environment,
            selected=case.selector if case else None,
            size="large",
            mode="performance" if label == "ordinary" else "correctness",
            target=target,
            allocation_mib=rl00bc_trials.STRICT[self.profile][0],
            shared_mib=64,
            workers=1,
            coverage=case is None and self.profile != "browser",
            instrument=True,
            justification=allowance,
            ancestor_deadline_ns=self.deadline,
        )
        attempt.update(
            {
                "status": "observed",
                "classification": record.get("classification"),
                "native_cases": record.get("native_cases"),
                "strict_verification": record.get("strict_verification"),
                "trial_record": str(path / "trial.json"),
            }
        )
        self.persist()
        return record

    def canonical(self, label: str, arm: str) -> dict[str, object]:
        record = self.trial(label, arm, None)
        rl00bc_corpus.verify(self.profile, "large", record.get("native_cases"))
        if record.get("classification") != "observed-success":
            invalid("canonical native comparison did not succeed")
        return record

    def strict(self, label: str, arm: str, cases: list[rl00bc_corpus.Case]) -> None:
        for case in cases:
            record = self.trial(label, arm, case)
            native = record.get("native_cases")
            if native:
                rl00bc_corpus.verify_selected(case, native)
            expected = (
                "own-boundary-resource-violation"
                if label == "excessive" and _target_case(self.profile, case, label)
                else "observed-success"
            )
            self.attempts[-1]["expected_classification"] = expected
            self.attempts[-1]["native_identity_observed"] = bool(native)
            self.attempts[-1]["matches_expected"] = record.get("classification") == expected
            self.persist()

    def compare(self, label: str, cases: list[rl00bc_corpus.Case]) -> None:
        matrix = cast(dict[str, dict[str, str]], self.summary["matrix"])
        matrix[label]["shared-worker"] = "in-progress"
        self.persist()
        shared = self.canonical(label, "shared-worker")
        matrix[label]["shared-worker"] = "observed"
        matrix[label]["full-fresh"] = "in-progress"
        self.persist()
        self.strict(label, "full-fresh", cases)
        matrix[label]["full-fresh"] = "observed"
        matrix[label]["selected"] = "in-progress"
        self.persist()
        native = self.canonical(label, "selected-canonical")
        rows = rl00bc_corpus.verify(self.profile, "large", native.get("native_cases"))
        shared_rows = rl00bc_corpus.verify(self.profile, "large", shared.get("native_cases"))
        if _outcomes(rows) != _outcomes(shared_rows):
            invalid("shared and selected canonical native outcomes differ")
        discovered: list[dict[str, object]] = [
            {"id": case.identity, "variant": case.variant} for case in cases
        ]
        scope = rl00bc_selection.build(self.context, discovered, [], first_adoption=True)
        selected = set(cast(list[str], scope["selected"]))
        if selected != {str(row["id"]) for row in rows}:
            invalid("first-adoption fallback did not cover the native corpus")
        scopes = cast(dict[str, object], self.summary["scopes"])
        scopes[label] = scope
        self.persist()
        self.strict(label, "selected-strict", [case for case in cases if case.identity in selected])
        matrix[label]["selected"] = "observed"
        self.persist()

    def run(self) -> dict[str, object]:
        cases = rl00bc_corpus.expected(self.profile, "large")
        try:
            for label in _LABELS:
                self.compare(label, cases)
            mismatches = [
                attempt for attempt in self.attempts if attempt.get("matches_expected") is False
            ]
            self.summary["status"] = (
                "comparisons-mismatch" if mismatches else "observed-with-required-proofs-pending"
            )
        except (OSError, ValueError, TypeError, RuntimeError, KeyError, AssertionError) as error:
            if self.attempts and self.attempts[-1]["status"] == "in-progress":
                self.attempts[-1]["status"] = "nonpass"
            _mark_incomplete(cast(dict[str, dict[str, str]], self.summary["matrix"]))
            self.summary["status"] = "incomplete"
            self.summary["error"] = f"{type(error).__name__}: {error}"[:1024]
        self.persist()
        return self.summary


def _outcomes(rows: list[dict[str, object]]) -> dict[str, object]:
    return {str(row["id"]): row.get("outcome") for row in rows}


def _mark_incomplete(matrix: dict[str, dict[str, str]]) -> None:
    for arms in matrix.values():
        for name, status in arms.items():
            if status == "in-progress":
                arms[name] = "incomplete"


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
    """Observe the three methods under a single caller-bound deadline."""
    rl00bc_corpus.expected(profile, "large")
    context = _context(environment)
    output.mkdir(parents=True, exist_ok=False)
    native_environment = {
        key: value for key, value in environment.items() if not key.startswith("RL00_CONTEXT_")
    }
    experiment = _Experiment(
        work,
        repo,
        scratch,
        output.absolute(),
        profile,
        native_environment,
        ancestor_deadline_ns,
        context,
    )
    experiment.summary = {
        "profile": profile,
        "size": "large",
        "labels": list(_LABELS),
        "context": context,
        "attempts": experiment.attempts,
        "scopes": {},
        "matrix": {
            label: dict.fromkeys(("shared-worker", "full-fresh", "selected"), "unrun")
            for label in _LABELS
        },
        "status": "in-progress",
        "selection": "first-adoption full fallback",
        "shared_worker_attribution": "unsupported: lifetime evidence is not case certification",
        "required_proofs_pending": [
            "case phase and child attribution",
            "shared fixture attribution and no-blame ordering",
            "reordering and cheap additions",
            "concurrent strict and nested capacity",
            "canonical coverage and scenario reconciliation",
            "narrow selection and cost",
            "small-corpus labeled comparison",
            "human adoption and usefulness calibration",
        ],
    }
    experiment.persist()
    return experiment.run()
