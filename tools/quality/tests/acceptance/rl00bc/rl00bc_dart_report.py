"""Validate native package:test events before using case-level evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from tests.acceptance.rl00bc.rl00bc_errors import invalid


@dataclass
class _Case:
    name: str
    source: str | None
    suite_id: int
    outcome: str | None = None
    hidden: bool | None = None
    errored: bool = False

    def result(
        self, identifier: int, output: Path, *, partial: bool = False, include_hidden: bool = False
    ) -> dict[str, object] | None:
        outcome = self.outcome or ("incomplete" if partial else "error")
        if self.errored and outcome in ("passed", "skipped"):
            outcome = "error"
        if not include_hidden and self.hidden is True and outcome in ("passed", "skipped"):
            return None
        return {
            "id": self.name,
            "native_id": identifier,
            "source": self.source,
            "suite_id": self.suite_id,
            "outcome": outcome,
            "visibility": "unknown"
            if self.hidden is None
            else "hidden"
            if self.hidden
            else "visible",
            "test_done": self.outcome is not None,
            "errored": self.errored,
            "native_report": str(output / "dart.json"),
            "raw_coverage": str(output / "coverage"),
        }


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        invalid(f"Dart event has no {label} object")
    return cast(dict[str, object], value)


def _integer(event: dict[str, object], key: str) -> int:
    value = event.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        invalid(f"Dart event has no integer {key}")
    return value


@dataclass
class _Stream:
    suites: dict[int, str | None] = field(default_factory=dict[int, str | None])
    cases: dict[int, _Case] = field(default_factory=dict[int, _Case])
    done: bool = False
    done_success: bool | None = None
    focused: bool = False

    def start(self, event: dict[str, object]) -> None:
        test = _object(event.get("test"), "test")
        identifier = _integer(test, "id")
        suite = _integer(test, "suiteID")
        name = test.get("name")
        if identifier in self.cases or suite not in self.suites or not isinstance(name, str):
            invalid("invalid or repeated Dart test start")
        self.cases[identifier] = _Case(name, self.suites[suite], suite)
        metadata = test.get("metadata")
        if isinstance(metadata, dict):
            self.focused |= (
                cast(dict[str, object], metadata).get("skipReason") == 'does not have "solo"'
            )

    def case(self, event: dict[str, object]) -> _Case:
        identifier = _integer(event, "testID")
        if identifier not in self.cases:
            invalid(f"Dart event names unknown test {identifier}")
        return self.cases[identifier]

    def complete(self, event: dict[str, object]) -> None:
        case = self.case(event)
        result = {"success": "passed", "failure": "failed", "error": "error"}.get(
            str(event.get("result"))
        )
        if case.outcome is not None or result is None:
            invalid(f"invalid or repeated Dart completion: {case.name}")
        case.outcome = "skipped" if result == "passed" and event.get("skipped") is True else result
        case.hidden = event.get("hidden") is True

    def read(self, value: object, *, partial: bool = False) -> None:
        event = _object(value, "event")
        kind = event.get("type")
        if kind == "suite":
            suite = _object(event.get("suite"), "suite")
            source = suite.get("path")
            self.suites[_integer(suite, "id")] = source if isinstance(source, str) else None
        elif kind == "testStart":
            self.start(event)
        elif kind == "testDone":
            self.complete(event)
        elif kind == "error":
            self.case(event).errored = True
        elif kind == "done":
            if self.done or (not partial and event.get("success") is not True):
                invalid("Dart completion is repeated or unsuccessful")
            self.done = True
            self.done_success = event.get("success") is True


def results(root: Path, output: Path, *, profile: str) -> list[dict[str, object]]:
    """Return native identities with core-equivalent result and completion handling."""
    if profile != "dart":
        invalid("expected dart profile")
    stream = _Stream()
    for line in (output / "dart.json").read_text(encoding="utf-8").splitlines():
        if line.strip():
            stream.read(json.loads(line))
    if not stream.done:
        invalid("Dart report has no done event")
    if stream.focused:
        invalid("focused Dart suite cannot provide canonical evidence")
    cases = [
        case
        for identifier, value in stream.cases.items()
        if (case := value.result(identifier, output)) is not None
    ]
    if not cases:
        invalid("Dart report has no visible cases")
    return cases


def _partial_stream(path: Path) -> tuple[_Stream, bool]:
    with path.open("rb") as source:
        data = source.read(1_048_577)
    if len(data) > 1_048_576:
        invalid("partial Dart report exceeds its byte bound")
    lines = data.splitlines(keepends=True)
    stream = _Stream()
    truncated = False
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            value: object = json.loads(line)
        except ValueError:
            if index != len(lines) - 1 or line.endswith(b"\n"):
                raise
            truncated = True
            break
        stream.read(value, partial=True)
    return stream, truncated


def partial(
    root: Path, output: Path, *, profile: str, kernel: dict[str, object]
) -> dict[str, object]:
    """Read surviving starts after a separately proven kernel resource stop."""
    if profile != "dart":
        invalid("expected dart profile")
    violation = kernel.get("resource_violation")
    if violation not in ("own-memory", "own-tasks", "ancestor-resource", "timeout"):
        invalid("partial Dart evidence requires a proven kernel resource stop")
    if kernel.get("success") is not False:
        invalid("partial Dart evidence cannot represent a successful kernel run")
    path = output / "dart.json"
    stream, truncated = _partial_stream(path)
    cases = [
        case
        for identifier, value in stream.cases.items()
        if (case := value.result(identifier, output, partial=True)) is not None
    ]
    starts = [
        value.result(identifier, output, partial=True, include_hidden=True)
        for identifier, value in stream.cases.items()
    ]
    return {
        "native_report": str(path),
        "native_cases": cases,
        "done": stream.done,
        "all_observed_starts": starts,
        "done_success": stream.done_success,
        "focused": stream.focused,
        "truncated_tail": truncated,
        "resource_violation": violation,
        "interpretation": "resource-stopped partial evidence",
    }
