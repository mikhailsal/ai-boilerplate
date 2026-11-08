"""Remote regression tests for interrupted Dart evidence and identity binding."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import cast

from tests.acceptance.rl00a.rl00a_cgroup import Group
from tests.acceptance.rl00bc import (
    rl00bc_dart_binding,
    rl00bc_event_binding,
    rl00bc_shared_oracle,
    rl00bc_trials,
)

_TARGET = "ordinary case"


def _suite() -> dict[str, object]:
    return {"type": "suite", "suite": {"id": 5, "path": "test/resource_a_test.dart"}}


def _start(identifier: int, name: str, *, focused: bool = False) -> dict[str, object]:
    metadata = {"skipReason": 'does not have "solo"' if focused else None}
    return {"type": "testStart", "test": {"id": identifier, "suiteID": 5, "name": name,
                                          "metadata": metadata}}


def _done(identifier: int, *, hidden: bool) -> dict[str, object]:
    return {"type": "testDone", "testID": identifier, "result": "success", "hidden": hidden}


def _row(report: dict[str, object], key: str, identifier: int) -> dict[str, object]:
    rows = cast(list[dict[str, object]], report[key])
    return next(row for row in rows if row["native_id"] == identifier)


class DartPartialEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "native").mkdir()

    def _parse(
        self, events: list[dict[str, object]], *, tail: str = ""
    ) -> tuple[list[dict[str, object]], str | None, dict[str, object], dict[str, object]]:
        data = "".join(json.dumps(event) + "\n" for event in [_suite(), *events]) + tail
        (self.root / "native/dart.json").write_text(data, encoding="utf-8")
        trial = rl00bc_trials._Trial(
            work=cast(Group, object()), repo=self.root, scratch=self.root, output=self.root,
            profile="dart", environment={}, selected=_TARGET, size="small", mode="correctness",
            target="native", allocation_mib=1, shared_mib=0, workers=1, coverage=False,
            instrument=True, justification=None, ancestor_deadline_ns=1, start_ns=0,
        )
        trial.root = self.root
        kernel: dict[str, object] = {
            "success": False, "cause": "own-memory", "resource_violation": "own-memory",
            "native_status": -9, "cleanup_complete": True,
        }
        cases, error = trial.parse(kernel)
        self.assertEqual(kernel["cause"], "own-memory")
        self.assertEqual(kernel["resource_violation"], "own-memory")
        self.assertEqual(kernel["native_status"], -9)
        self.assertEqual(rl00bc_trials._classification(kernel, cases, error),
                         "own-boundary-resource-violation")
        self.assertIsNotNone(trial.partial_native)
        return cases, error, cast(dict[str, object], trial.partial_native), kernel

    def _assert_unbound(self, cases: list[dict[str, object]], error: str | None) -> None:
        self.assertIsNotNone(error)
        record = {"native_cases": cases, "parse_error": error, "selection_error": error}
        self.assertFalse(rl00bc_event_binding.report_has(record, _TARGET, "default", single=True))

    def test_completed_hidden_loader_and_actual_target_start(self) -> None:
        cases, error, report, _ = self._parse([
            _start(1, "loading test/resource_a_test.dart"), _done(1, hidden=True),
            _start(42, _TARGET),
        ])
        self.assertIsNone(error)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["id"], _TARGET)
        self.assertEqual(cases[0]["native_id"], 42)
        self.assertEqual(cases[0]["source"], "test/resource_a_test.dart")
        self.assertEqual(cases[0]["outcome"], "incomplete")
        self.assertIs(cases[0]["test_done"], False)
        self.assertEqual(_row(report, "all_observed_starts", 1)["visibility"], "hidden")
        self.assertEqual(_row(report, "all_observed_starts", 42)["visibility"], "unknown")
        self.assertTrue(rl00bc_event_binding.report_has({"native_cases": cases}, _TARGET,
                                                        "default", single=True))

    def test_incomplete_loader_is_not_silently_hidden(self) -> None:
        cases, error, report, _ = self._parse([
            _start(1, "loading test/resource_a_test.dart"), _start(42, _TARGET),
        ])
        self._assert_unbound(cases, error)
        loader = _row(report, "all_observed_starts", 1)
        self.assertEqual(loader["visibility"], "unknown")
        self.assertEqual(loader["outcome"], "incomplete")
        self.assertEqual(_row(report, "all_observed_starts", 42)["native_id"], 42)

    def test_genuine_extra_visible_case_prevents_exclusive_binding(self) -> None:
        cases, error, report, _ = self._parse([
            _start(7, "unexpected case"), _done(7, hidden=False), _start(42, _TARGET),
        ])
        self._assert_unbound(cases, error)
        self.assertEqual(_row(report, "all_observed_starts", 7)["visibility"], "visible")
        self.assertEqual(_row(report, "all_observed_starts", 7)["outcome"], "passed")
        self.assertEqual(_row(report, "all_observed_starts", 42)["outcome"], "incomplete")

    def test_stop_before_target_does_not_invent_identity(self) -> None:
        cases, error, report, _ = self._parse([
            _start(1, "loading test/resource_a_test.dart"), _done(1, hidden=True),
        ])
        self._assert_unbound(cases, error)
        self.assertEqual(cases, [])
        self.assertEqual(len(cast(list[object], report["all_observed_starts"])), 1)

    def test_focused_stream_is_not_certified(self) -> None:
        cases, error, report, _ = self._parse([_start(42, _TARGET, focused=True)])
        self._assert_unbound(cases, error)
        self.assertIs(report["focused"], True)
        self.assertEqual(_row(report, "all_observed_starts", 42)["native_id"], 42)

    def test_truncated_final_json_is_not_certified(self) -> None:
        cases, error, report, _ = self._parse([_start(42, _TARGET)], tail='{"type":"testDone"')
        self._assert_unbound(cases, error)
        self.assertIs(report["truncated_tail"], True)
        self.assertEqual(_row(report, "all_observed_starts", 42)["outcome"], "incomplete")

    def test_error_before_stop_is_preserved_as_incomplete(self) -> None:
        cases, _, report, _ = self._parse([
            _start(42, _TARGET), {"type": "error", "testID": 42, "error": "fixture failed"},
        ])
        self.assertEqual(len(cases), 1)
        target = _row(report, "all_observed_starts", 42)
        self.assertIs(target["errored"], True)
        self.assertIs(target["test_done"], False)
        self.assertEqual(target["outcome"], "incomplete")
        self.assertIs(report["done"], False)


class DartSourceBindingTests(unittest.TestCase):
    def test_actual_sources_match_across_roots_without_equating_ids(self) -> None:
        canonical: dict[str, object] = {"corpus_root": "/tmp/run-a", "native_cases": [
            {"id": _TARGET, "source": "/tmp/run-a/test/resource_a_test.dart", "native_id": 11}
        ]}
        strict: dict[str, object] = {"corpus_root": "/tmp/run-b", "native_cases": [
            {"id": _TARGET, "source": "/tmp/run-b/test/resource_a_test.dart", "native_id": 73,
             "outcome": "incomplete"}
        ]}
        result = rl00bc_dart_binding.compare(canonical, strict, _TARGET, "default")
        self.assertIs(result["bound"], True)
        self.assertEqual(result["canonical_native_id"], 11)
        self.assertEqual(result["strict_native_id"], 73)
        self.assertEqual(result["canonical_source"], "test/resource_a_test.dart")

    def test_different_or_unavailable_source_is_not_bound(self) -> None:
        canonical: dict[str, object] = {"corpus_root": "/tmp/run-a", "native_cases": [
            {"id": _TARGET, "source": "/tmp/run-a/test/resource_a_test.dart", "native_id": 11}
        ]}
        strict: dict[str, object] = {"corpus_root": "/tmp/run-b", "native_cases": [
            {"id": _TARGET, "source": "/tmp/run-b/test/resource_b_test.dart", "native_id": 73}
        ]}
        self.assertIs(rl00bc_dart_binding.compare(canonical, strict, _TARGET, "default")["bound"],
                      False)
        strict["native_cases"] = [{"id": _TARGET, "source": None, "native_id": 73}]
        self.assertIs(rl00bc_dart_binding.compare(canonical, strict, _TARGET, "default")["bound"],
                      False)

    def test_parse_or_selection_error_blocks_report_binding(self) -> None:
        cases = [{"id": _TARGET, "outcome": "incomplete"}]
        for field in ("parse_error", "selection_error"):
            self.assertFalse(rl00bc_event_binding.report_has(
                {"native_cases": cases, field: "ambiguous"}, _TARGET, "default", single=True
            ))


def _shared_event(context: str, phase: str, stamp: int) -> dict[str, object]:
    return {
        "case": "retained", "phase": phase, "variant": "retained", "pid": 501,
        "fixture_context": context, "monotonic_ns": str(stamp),
    }


def _shared_pair(context: str, stamp: int) -> list[dict[str, object]]:
    return [
        _shared_event(context, "retained-allocation-start", stamp),
        _shared_event(context, "retained-allocation-end", stamp + 1),
    ]


class NodeSharedFixtureTests(unittest.TestCase):
    def test_same_pid_contexts_are_partitioned_and_selected_across_roots(self) -> None:
        canonical: dict[str, object] = {"corpus_root": "/tmp/canonical"}
        strict: dict[str, object] = {"corpus_root": "/tmp/strict"}
        first = "node:file:///tmp/canonical/resource_a.test.mjs"
        selected = "node:file:///tmp/canonical/resource_b.test.mjs"
        strict_first = "node:file:///tmp/strict/resource_a.test.mjs"
        strict_selected = "node:file:///tmp/strict/resource_b.test.mjs"
        canonical_events = [*_shared_pair(first, 1), *_shared_pair(selected, 3)]
        strict_events = [*_shared_pair(strict_first, 5), *_shared_pair(strict_selected, 7)]
        case: list[dict[str, object]] = [{
            "case": "ordinary", "phase": "call-start", "pid": 501,
            "fixture_context": selected, "monotonic_ns": "9",
        }]
        before, after, report = rl00bc_shared_oracle.select(
            "node", canonical, strict, canonical_events, strict_events, case
        )
        self.assertEqual(before, _shared_pair(selected, 3))
        self.assertEqual(after, _shared_pair(strict_selected, 7))
        self.assertEqual(report["selected_context"], "node:resource_b.test.mjs")
        self.assertIs(report["context_bound"], True)
        self.assertIs(report["canonical_all_ordered"], True)
        instances = cast(list[dict[str, object]], report["canonical_instances"])
        self.assertEqual(len(instances), 2)
        self.assertEqual({item["context"] for item in instances},
                         {"node:resource_a.test.mjs", "node:resource_b.test.mjs"})
        self.assertTrue(all(item["pid"] == 501 and item["ordered_setup"] is True
                            for item in instances))

    def test_missing_or_ambiguous_case_context_remains_unproved(self) -> None:
        canonical: dict[str, object] = {"corpus_root": "/tmp/canonical"}
        strict: dict[str, object] = {"corpus_root": "/tmp/strict"}
        first = "node:file:///tmp/canonical/resource_a.test.mjs"
        second = "node:file:///tmp/canonical/resource_b.test.mjs"
        events = [*_shared_pair(first, 1), *_shared_pair(second, 3)]
        other = _shared_pair("node:file:///tmp/strict/resource_a.test.mjs", 5)
        missing: list[dict[str, object]] = []
        ambiguous: list[dict[str, object]] = [{"fixture_context": first}, {"fixture_context": second}]
        for cases in (missing, ambiguous):
            before, after, report = rl00bc_shared_oracle.select(
                "node", canonical, strict, events, other, cases
            )
            self.assertEqual(before, [])
            self.assertEqual(after, [])
            self.assertIsNone(report["selected_context"])
            self.assertIs(report["context_bound"], False)
            self.assertIn("selected case has no unique observed fixture context",
                          cast(list[str], report["gaps"]))

    def test_missing_retained_event_context_cannot_bind_case(self) -> None:
        canonical: dict[str, object] = {"corpus_root": "/tmp/canonical"}
        strict: dict[str, object] = {"corpus_root": "/tmp/strict"}
        selected = "node:file:///tmp/canonical/resource_a.test.mjs"
        events = _shared_pair(selected, 1)
        for event in events:
            event.pop("fixture_context")
        strict_events = _shared_pair("node:file:///tmp/strict/resource_a.test.mjs", 3)
        before, _, report = rl00bc_shared_oracle.select(
            "node", canonical, strict, events, strict_events, [{"fixture_context": selected}]
        )
        self.assertEqual(before, [])
        self.assertIs(report["context_bound"], False)
        self.assertIn("retained fixture lacks actual PID or source/project context",
                      cast(list[str], report["gaps"]))


if __name__ == "__main__":
    unittest.main()
