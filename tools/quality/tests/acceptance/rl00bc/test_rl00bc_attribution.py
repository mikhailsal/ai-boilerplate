"""Remote regression tests for case, phase, and shared-resource attribution."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import cast

from tests.acceptance.rl00bc import rl00bc_comparison_oracle, rl00bc_phase_oracle

_LEAF = "/sys/fs/cgroup/quality-attribution-fixture/leaf"
_MEMBER = "0::/quality-attribution-fixture/leaf\n"
_CONTEXT = "test_subject.py::retained"
_PHASES = ("setup-start", "setup-end", "call-start", "call-end", "teardown-start", "teardown-end")


def _snapshot(oom: int) -> dict[str, object]:
    return {"path": _LEAF, "inode": 867, "memory.events.local": {"oom": oom, "oom_kill": 0}}


def _event(variant: str, phase: str, stamp: int, oom: int) -> dict[str, object]:
    return {
        "label": variant,
        "variant": variant,
        "phase": phase,
        "pid": 1234,
        "native_id": f"test_subject.py::test_subject[{variant}]",
        "fixture_context": _CONTEXT,
        "monotonic_ns": stamp,
        "resource_observation": {
            "cgroup": _MEMBER,
            "cgroup_inode": 867,
            "memory_events_local": {"oom": oom, "oom_kill": 0},
        },
    }


def _shared(phase: str, stamp: int, oom: int) -> dict[str, object]:
    row = _event("retained", phase, stamp, oom)
    row.pop("native_id")
    return row


def _part(value: dict[str, object], name: str) -> dict[str, object]:
    return cast(dict[str, object], value[name])


class AttributionEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def _files(self, name: str, rows: list[dict[str, object]]) -> Path:
        directory = self.root / name
        directory.mkdir()
        for index, row in enumerate(rows):
            (directory / f"event-{index}.json").write_text(json.dumps(row), encoding="utf-8")
        return directory

    def _runs(
        self,
        *,
        variant: str = "ordinary",
        canonical_rows: list[dict[str, object]] | None = None,
        strict_rows: list[dict[str, object]] | None = None,
    ) -> tuple[dict[str, object], dict[str, object], str]:
        canonical_rows = (
            canonical_rows
            if canonical_rows is not None
            else [_event(variant, phase, index + 1, 0) for index, phase in enumerate(_PHASES)]
        )
        strict_rows = (
            strict_rows if strict_rows is not None else [_event(variant, "call-start", 10, 0)]
        )
        identity = f"test_subject::test_subject[{variant}]"
        canonical: dict[str, object] = {
            "events": str(self._files("canonical", canonical_rows)),
            "corpus_root": str(self.root),
            "native_cases": [{"id": identity, "variant": variant, "outcome": "passed"}],
            "selected": None,
            "scope": "canonical-suite",
            "classification": "observed-success",
            "parse_error": None,
            "selection_error": None,
        }
        strict: dict[str, object] = {
            "events": str(self._files("strict", strict_rows)),
            "corpus_root": str(self.root),
            "native_cases": [],
            "parse_error": None,
            "selection_error": None,
            "selected": variant,
            "scope": "selected-case",
            "classification": "own-boundary-resource-violation",
            "kernel": {
                "cause": "own-memory",
                "resource_violation": "own-memory",
                "success": False,
                "native_status": -9,
                "cleanup_complete": True,
                "before": _snapshot(0),
                "after": _snapshot(1),
            },
        }
        return canonical, strict, identity

    def _evaluate(
        self,
        canonical: dict[str, object],
        strict: dict[str, object],
        identity: str,
        *,
        target: str = "native",
        variant: str = "ordinary",
    ) -> dict[str, object]:
        result = rl00bc_phase_oracle.evaluate(
            "python", target, identity, variant, canonical, strict
        )
        self.assertEqual(result["resource_classification"], "own-boundary-resource-violation")
        self.assertEqual(result["kernel_cause"], "own-memory")
        self.assertEqual(result["native_status"], _part(strict, "kernel")["native_status"])
        return result

    def test_unique_target_event_bridges_known_resource_stop(self) -> None:
        canonical, strict, identity = self._runs()
        result = self._evaluate(canonical, strict, identity)
        binding = _part(result, "identity_binding")
        self.assertIs(binding["strict_scope_valid"], True)
        self.assertIs(binding["event_exclusivity"], True)
        self.assertIs(result["strict_identity_bound"], True)
        self.assertTrue(rl00bc_comparison_oracle.matches(result, memory=True))

    def test_parser_failure_and_another_case_do_not_bind_target(self) -> None:
        rows = [_event("ordinary", "call-start", 10, 0), _event("other", "call-start", 11, 0)]
        canonical, strict, identity = self._runs(strict_rows=rows)
        strict["parse_error"] = "native report invalid"
        result = self._evaluate(canonical, strict, identity)
        binding = _part(result, "identity_binding")
        self.assertIs(binding["strict_scope_valid"], False)
        self.assertIs(binding["event_exclusivity"], False)
        self.assertIs(result["strict_identity_bound"], False)
        self.assertFalse(rl00bc_comparison_oracle.matches(result, memory=True))

    def test_oom_after_completed_call_is_not_call_phase_evidence(self) -> None:
        rows = [_event("ordinary", "call-start", 10, 0), _event("ordinary", "call-end", 11, 0)]
        canonical, strict, identity = self._runs(strict_rows=rows)
        result = self._evaluate(canonical, strict, identity)
        memory = _part(_part(_part(result, "evidence"), "resource"), "memory")
        self.assertIs(memory["oom_growth_within_phase"], False)
        self.assertFalse(rl00bc_comparison_oracle.matches(result, memory=True))

    def test_caught_oom_between_call_start_and_end_is_phase_evidence(self) -> None:
        rows = [_event("ordinary", "call-start", 10, 0), _event("ordinary", "call-end", 11, 1)]
        canonical, strict, identity = self._runs(strict_rows=rows)
        _part(strict, "kernel")["native_status"] = 0
        result = self._evaluate(canonical, strict, identity)
        memory = _part(_part(_part(result, "evidence"), "resource"), "memory")
        self.assertIs(memory["oom_growth_within_phase"], True)
        self.assertTrue(rl00bc_comparison_oracle.matches(result, memory=True))

    def test_later_phase_cannot_close_a_missing_call_end(self) -> None:
        rows = [
            _event("ordinary", "call-start", 10, 0),
            _event("ordinary", "teardown-start", 11, 0),
        ]
        canonical, strict, identity = self._runs(strict_rows=rows)
        result = self._evaluate(canonical, strict, identity)
        self.assertFalse(rl00bc_comparison_oracle.matches(result, memory=True))

    def test_duplicate_call_end_is_ambiguous(self) -> None:
        rows = [
            _event("ordinary", "call-start", 10, 0),
            _event("ordinary", "call-end", 11, 1),
            _event("ordinary", "call-end", 12, 1),
        ]
        canonical, strict, identity = self._runs(strict_rows=rows)
        result = self._evaluate(canonical, strict, identity)
        self.assertFalse(rl00bc_comparison_oracle.matches(result, memory=True))

    def test_incomplete_cleanup_keeps_raw_cause_but_blocks_comparison(self) -> None:
        canonical, strict, identity = self._runs()
        _part(strict, "kernel")["cleanup_complete"] = False
        result = self._evaluate(canonical, strict, identity)
        self.assertFalse(rl00bc_comparison_oracle.matches(result, memory=True))

    def test_missing_counter_cannot_prove_phase_growth(self) -> None:
        row = _event("ordinary", "call-start", 10, 0)
        _part(row, "resource_observation")["memory_events_local"] = {"oom": 0}
        canonical, strict, identity = self._runs(strict_rows=[row])
        result = self._evaluate(canonical, strict, identity)
        self.assertFalse(rl00bc_comparison_oracle.matches(result, memory=True))

    def _retained_runs(
        self, *, incomplete_case: bool = False
    ) -> tuple[dict[str, object], dict[str, object], str]:
        phases = _PHASES[:-1] if incomplete_case else _PHASES
        canonical = [_shared("session-setup-start", 1, 0), _shared("session-setup", 2, 0)]
        canonical += [_event("retained", phase, index + 3, 0) for index, phase in enumerate(phases)]
        strict = [_shared("session-setup-start", 10, 0)]
        return self._runs(variant="retained", canonical_rows=canonical, strict_rows=strict)

    def test_shared_selection_error_prevents_comparison(self) -> None:
        canonical, strict, identity = self._retained_runs()
        strict["selection_error"] = "unexpected native identity"
        result = self._evaluate(canonical, strict, identity, target="retained", variant="retained")
        self.assertFalse(rl00bc_comparison_oracle.matches(result, memory=False, shared=True))
        self.assertEqual(result["case_attribution"], "unproved")

    def test_shared_canonical_case_must_complete(self) -> None:
        canonical, strict, identity = self._retained_runs(incomplete_case=True)
        result = self._evaluate(canonical, strict, identity, target="retained", variant="retained")
        self.assertFalse(rl00bc_comparison_oracle.matches(result, memory=False, shared=True))
        self.assertEqual(result["case_attribution"], "unproved")

    def test_shared_evidence_remains_separate_from_case_attribution(self) -> None:
        canonical, strict, identity = self._retained_runs()
        result = self._evaluate(canonical, strict, identity, target="retained", variant="retained")
        self.assertTrue(rl00bc_comparison_oracle.matches(result, memory=False, shared=True))
        self.assertEqual(result["case_attribution"], "unproved")
        shared = _part(_part(result, "evidence"), "shared_fixture_contexts")
        self.assertIs(shared["context_bound"], True)

    def test_oversized_event_makes_comparison_unproved(self) -> None:
        canonical, strict, identity = self._runs()
        directory = Path(cast(str, strict["events"]))
        (directory / "oversized.json").write_text(" " * 16_385, encoding="utf-8")
        result = self._evaluate(canonical, strict, identity)
        self.assertIs(_part(result, "evidence")["event_files_valid"], False)
        self.assertFalse(rl00bc_comparison_oracle.matches(result, memory=False))

    def test_malformed_event_makes_comparison_unproved(self) -> None:
        canonical, strict, identity = self._runs()
        directory = Path(cast(str, strict["events"]))
        (directory / "malformed.json").write_text("{", encoding="utf-8")
        result = self._evaluate(canonical, strict, identity)
        self.assertIs(_part(result, "evidence")["event_files_valid"], False)
        self.assertFalse(rl00bc_comparison_oracle.matches(result, memory=False))


if __name__ == "__main__":
    unittest.main()
