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
    outcome: str | None = None
    hidden: bool = False
    errored: bool = False

    def result(self, identifier: int, output: Path) -> dict[str, object] | None:
        outcome = self.outcome or "error"
        if self.errored and outcome in ("passed", "skipped"):
            outcome = "error"
        if self.hidden and outcome in ("passed", "skipped"):
            return None
        return {
            "id": self.name,
            "native_id": identifier,
            "outcome": outcome,
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
    suites: set[int] = field(default_factory=set[int])
    cases: dict[int, _Case] = field(default_factory=dict[int, _Case])
    done: bool = False
    focused: bool = False

    def start(self, event: dict[str, object]) -> None:
        test = _object(event.get("test"), "test")
        identifier = _integer(test, "id")
        suite = _integer(test, "suiteID")
        name = test.get("name")
        if identifier in self.cases or suite not in self.suites or not isinstance(name, str):
            invalid("invalid or repeated Dart test start")
        self.cases[identifier] = _Case(name)
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

    def read(self, value: object) -> None:
        event = _object(value, "event")
        kind = event.get("type")
        if kind == "suite":
            self.suites.add(_integer(_object(event.get("suite"), "suite"), "id"))
        elif kind == "testStart":
            self.start(event)
        elif kind == "testDone":
            self.complete(event)
        elif kind == "error":
            self.case(event).errored = True
        elif kind == "done":
            if self.done or event.get("success") is not True:
                invalid("Dart completion is repeated or unsuccessful")
            self.done = True


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
    cases = [case for identifier, value in stream.cases.items()
             if (case := value.result(identifier, output)) is not None]
    if not cases:
        invalid("Dart report has no visible cases")
    return cases
