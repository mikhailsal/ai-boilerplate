"""Implement the finite Git-candidate pressure comparison inside a guarded controller."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from quality.gitio import Candidate, Repository, materialize
from quality.gitio.candidate import staged

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import (
    rl00bc_candidate_changes,
    rl00bc_kernel,
    rl00bc_pressure_fixture as fixture,
    rl00bc_selection,
)
from tests.acceptance.rl00bc.rl00bc_errors import invalid
from tests.acceptance.rl00bc.rl00bc_pressure_fixture import (
    collect_events,
    discovered_ids,
    kernel_success,
    object_value,
    pressure_target,
    validate_events,
    validate_limits,
    verify_own_oom,
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hash(repo: Path) -> str:
    paths = (
        "tools/quality/tests/acceptance/rl00bc/rl00bc_pressure.py",
        "tools/quality/tests/acceptance/rl00bc/rl00bc_pressure_worker.py",
        "tools/quality/tests/acceptance/rl00bc/rl00bc_pressure_fixture.py",
        "tools/quality/tests/acceptance/rl00bc/rl00bc_candidate_changes.py",
        "tools/quality/tests/acceptance/rl00bc/rl00bc_selection.py",
        "tools/quality/tests/acceptance/rl00bc/rl00bc_kernel.py",
        "tools/quality/src/quality/gitio/candidate.py",
        "tools/quality/src/quality/gitio/repo.py",
        "tools/quality/src/quality/gitio/snapshot.py",
        "tools/quality/src/quality/gitio/diff.py",
    )
    value = hashlib.sha256()
    for name in paths:
        value.update(name.encode() + b"\0" + _hash(repo / name).encode() + b"\n")
    return value.hexdigest()


def save_record(path: Path, value: object) -> None:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > 1_048_576:
        invalid("pressure evidence exceeds the finite record bound")
    path.write_bytes(data)


def _git(root: Path, env: dict[str, str], *argv: str) -> str:
    result = subprocess.run(
        ["git", *argv], cwd=root, env=env, capture_output=True, timeout=4, check=True
    )
    if len(result.stdout) > 65536 or len(result.stderr) > 65536:
        invalid("Git fixture output exceeds its bound")
    return result.stdout.decode("utf-8").strip()


@dataclass
class PressureExperiment:
    work: Group
    repo: Path
    scratch: Path
    output: Path
    python: Path
    deadline: int
    root: Path = field(init=False)
    git_env: dict[str, str] = field(init=False)
    repository: Repository = field(init=False)
    evidence: dict[str, object] = field(default_factory=dict[str, object])

    def guard(self) -> None:
        if time.monotonic_ns() >= self.deadline:
            invalid("pressure experiment exceeded its absolute deadline")

    def initialize(self) -> None:
        self.root = self.scratch / "git-fixture"
        self.root.mkdir(parents=True, exist_ok=False)
        home = self.scratch / "home"
        home.mkdir(parents=True, exist_ok=False)
        self.git_env = {"HOME": str(home), "PATH": "/usr/local/bin:/usr/bin:/bin",
                        "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1"}
        _git(
            self.root, self.git_env, "init", "--quiet", "--initial-branch=main",
        )
        _git(self.root, self.git_env, "config", "user.name", "RL00 fixture")
        _git(self.root, self.git_env, "config", "user.email", "rl00@example.invalid")
        files = (("support.py", fixture.SUPPORT), ("test_pressure.py", fixture.PRESSURE_TEST),
                 ("test_cheap.py", fixture.CHEAP_BASE), ("data.txt", "1\n"))
        for name, text in files:
            (self.root / name).write_text(text, encoding="utf-8")
        _git(self.root, self.git_env, "add", ".")
        _git(self.root, self.git_env, "commit", "--quiet", "-m", "fixture base")
        self.repository = Repository.discover(self.root, self.git_env)
        (self.output / "native-runner.py").write_text(fixture.RUNNER, encoding="utf-8")
        self.evidence.update({"base_commit": _git(self.root, self.git_env, "rev-parse", "HEAD"),
                              "runner_sha256": _hash(self.output / "native-runner.py")})

    def discover(self, candidate: Candidate, label: str) -> list[dict[str, object]]:
        self.guard()
        return rl00bc_candidate_changes.collect(self.repository, candidate, self.output / label)

    def scope(self, candidate: Candidate, cases: list[dict[str, object]], *, first: bool,
              trusted: bool) -> dict[str, object]:
        actual = rl00bc_candidate_changes.read(
            self.repository, candidate, cases, comparison_trusted=trusted,
            independent_fixture_files=frozenset({"test_cheap.py"}),
        )
        context: dict[str, object] = {
            "candidate": candidate.tree, "base": candidate.base_tree, "tested_tree": candidate.tree,
            "policy": _hash(self.repo / "quality.toml"), "runtime": _hash(self.python),
            "source": _source_hash(self.repo), "runtime_path": str(self.python),
            "comparison_trusted": trusted,
            "native_file_mapping_complete": actual["native_file_mapping_complete"],
            "independent_fixture_files": actual["independent_fixture_files"],
        }
        changes = cast(list[dict[str, str]], actual["changes"])
        scope = rl00bc_selection.build(context, cases, changes, first_adoption=first)
        rl00bc_selection.verify(scope, context, cases, cast(list[str], scope["selected"]))
        return {"actual": actual, "scope": scope}

    def native(
        self, root: Path, label: str, ids: list[str], memory: int, tasks: int
    ) -> dict[str, object]:
        self.guard()
        directory = self.output / label
        directory.mkdir()
        events = directory / "events"
        events.mkdir()
        env = {"HOME": str(self.scratch / "home"), "PATH": "/usr/local/bin:/usr/bin:/bin",
               "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1",
               "PRESSURE_EVENTS": str(events)}
        raw = rl00bc_kernel.execute(
            self.work, [str(self.python), str(self.output / "native-runner.py"), json.dumps(ids),
                        str(directory / "native-result.json")], root, env, directory / "kernel",
            memory_mib=memory, tasks=tasks, native_seconds=10,
            ancestor_deadline_ns=self.deadline, payload_deadline_ns=self.deadline - 3_000_000_000,
        )
        self.evidence[label] = {"kernel_path": str(directory / "kernel/result.json"),
                                "event_directory": str(events), "kernel": raw}
        save_record(self.output / "progress.json", self.evidence)
        validate_limits(raw, memory, tasks)
        return {"kernel": raw, "memory_mib": memory, "tasks": tasks, "ids": ids,
                "events": collect_events(events, root.resolve(), raw), "event_directory": str(events),
                "kernel_path": str(directory / "kernel/result.json"),
                "native_result": str(directory / "native-result.json"),
                "deadline_ns": self.deadline}

    def baseline(self) -> tuple[str, list[str]]:
        candidate = staged(self.repository)
        cases = self.discover(candidate, "baseline-discovery")
        target = pressure_target(cases)
        with materialize(self.repository, candidate.tree) as snapshot:
            digest = _hash(snapshot.root / "data.txt")
            observation = self.native(snapshot.root, "baseline-strict", [target], 48, 8)
            raw = object_value(observation["kernel"])
            validate_events(cast(list[dict[str, object]], observation["events"]), [target], target,
                      digest, 1, complete=True)
            if not kernel_success(raw):
                invalid("unmodified input did not pass the strict leaf")
            candidate.verify_unchanged()
        self.evidence["baseline"] = {"tree": candidate.tree, "base_tree": candidate.base_tree,
                                     "input_sha256": digest, "observation": observation}
        return target, discovered_ids(cases)

    def narrow(self, target: str) -> list[str]:
        (self.root / "test_cheap.py").write_text(fixture.CHEAP_CHANGED, encoding="utf-8")
        _git(self.root, self.git_env, "add", "test_cheap.py")
        candidate = staged(self.repository)
        cases = self.discover(candidate, "narrow-discovery")
        if pressure_target(cases) != target:
            invalid("unchanged pressure identity drifted")
        observation = self.scope(candidate, cases, first=False, trusted=True)
        selected = cast(list[str], object_value(observation["scope"])["selected"])
        expected = sorted(
            cast(str, case["id"]) for case in cases if case.get("file") == "test_cheap.py"
        )
        if selected != expected or target in selected or len(selected) != 6:
            invalid("explicit independent test-file selection was not narrow")
        self.evidence["narrow"] = observation
        return discovered_ids(cases)

    def mutated(self, target: str, original: list[str], narrow_ids: list[str]) -> None:
        (self.root / "data.txt").write_text("72\n", encoding="utf-8")
        _git(self.root, self.git_env, "add", "data.txt")
        candidate = staged(self.repository)
        cases = self.discover(candidate, "changed-discovery")
        ids = discovered_ids(cases)
        if pressure_target(cases) != target or ids != narrow_ids or not set(original) <= set(ids):
            invalid("cheap additions or reordering hid an original identity")
        if len(ids) != 7:
            invalid("changed native discovery has an unexpected case count")
        self.full_scopes(candidate, cases, ids)
        self.compare(candidate, ids, target)

    def full_scopes(
        self, candidate: Candidate, cases: list[dict[str, object]], ids: list[str]
    ) -> None:
        records = {"changed": self.scope(candidate, cases, first=False, trusted=True),
                   "first_adoption": self.scope(candidate, cases, first=True, trusted=True),
                   "untrusted": self.scope(candidate, cases, first=False, trusted=False)}
        if any(object_value(record["scope"]).get("selected") != ids for record in records.values()):
            invalid("changed data, first adoption, or unknown influence did not select all cases")
        if (object_value(records["first_adoption"]["scope"]).get("reason") != "first-adoption-full"
                or object_value(records["untrusted"]["scope"]).get("reason")
                != "untrusted-comparison-full"):
            invalid("first adoption or untrusted comparison did not use the expected fallback")
        actual = object_value(records["changed"]["actual"])
        changes = cast(list[dict[str, str]], actual["actual_git_changes"])
        if {change.get("path") for change in changes} != {"data.txt", "test_cheap.py"}:
            invalid("candidate Git changes did not include the expected input and cheap cases")
        self.evidence["full_scopes"] = records

    def compare(self, candidate: Candidate, ids: list[str], target: str) -> None:
        candidate.verify_unchanged()
        with materialize(self.repository, candidate.tree) as snapshot:
            root = snapshot.root
            digest = _hash(root / "data.txt")
            hashes = {name: _hash(root / name) for name in
                      ("data.txt", "test_pressure.py", "test_cheap.py", "support.py")}
            order = list(reversed(ids))
            canonical = self.native(root, "changed-canonical", order, 256, 16)
            canonical_raw = object_value(canonical["kernel"])
            validate_events(cast(list[dict[str, object]], canonical["events"]), order, target, digest,
                      72, complete=True)
            if not kernel_success(canonical_raw):
                invalid("changed canonical suite did not complete successfully")
            strict = self.native(root, "changed-strict", [target], 48, 8)
            strict_raw = object_value(strict["kernel"])
            validate_events(cast(list[dict[str, object]], strict["events"]), [target], target, digest,
                      72, complete=False)
            verify_own_oom(strict_raw, cast(list[dict[str, object]], strict["events"]), target)
            candidate.verify_unchanged()
        self.evidence["comparison"] = {
            "candidate_tree": candidate.tree, "base_tree": candidate.base_tree,
            "snapshot_sha256": hashes, "native_target": target, "reversed_order": order,
            "canonical": canonical, "strict": strict,
        }
