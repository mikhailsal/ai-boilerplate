"""Pin the RL00b/c driver pass rules to the result shapes the phases really produce."""

from __future__ import annotations

import unittest
from typing import cast

from tests.acceptance.rl00bc import rl00bc_adoption, rl00bc_driver, rl00bc_outside

_FINAL = rl00bc_adoption.FINAL_PHASE


def _partial(status: str) -> dict[str, object]:
    # Lifecycle, nested and faults start with success=False and never raise it, because
    # other required proofs stay pending; observed-partial is their best state.
    return {"status": status, "success": False, "required_proofs_pending": ["pending proof"]}


def _native(*, success: bool = True, cleanup: bool = True) -> dict[str, object]:
    return {
        "argv": ["/usr/bin/git", "status"],
        "cwd": "/scratch",
        "evidence": "/output/phase/result.json",
        "success": success,
        "cause": None,
        "native_status": 0,
        "cleanup_complete": cleanup,
        "elapsed_seconds": 1.0,
    }


def _chain(*names: str) -> dict[str, object]:
    # adopt() always records the missing-delegation proof as deliberately unrun.
    phases: dict[str, object] = {
        rl00bc_adoption.UNRUN_PROOF: {"status": "unrun", "reason": "no undelegated branch"}
    }
    phases.update({name: _native() for name in names})
    return {"phases": phases, "required_gaps": ["human usability is unmeasured"]}


def _phases(result: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], result["phases"])


def _passed(phase: str, result: dict[str, object]) -> bool:
    return rl00bc_driver.comparison_passed(phase, result)


class SingleVerdictTests(unittest.TestCase):
    def test_prepare_passes_only_when_prepared(self) -> None:
        self.assertTrue(_passed("prepare", {"prepared": True}))
        self.assertFalse(_passed("prepare", {"prepared": False}))
        self.assertFalse(_passed("prepare", {}))

    def test_correctness_requires_the_pending_proof_verdict(self) -> None:
        verdict = "comparisons-passed-external-proofs-pending"
        self.assertTrue(_passed("correctness", {"verdict": verdict}))
        self.assertFalse(_passed("correctness", {"verdict": "comparisons-failed"}))
        self.assertFalse(_passed("correctness", {}))

    def test_compatibility_requires_pass(self) -> None:
        self.assertTrue(_passed("compatibility", {"verdict": "pass"}))
        self.assertFalse(_passed("compatibility", {"verdict": "unproved"}))
        self.assertFalse(_passed("compatibility", {}))

    def test_methods_require_the_observed_status(self) -> None:
        status = "observed-with-required-proofs-pending"
        self.assertTrue(_passed("methods", {"status": status}))
        self.assertFalse(_passed("methods", {"status": "comparisons-mismatch"}))
        self.assertFalse(_passed("methods", {"status": "incomplete"}))

    def test_measure_requires_every_timing_cell_to_pass(self) -> None:
        status = "timing-cells-pass-required-proofs-pending"
        self.assertTrue(_passed("measure", {"status": status}))
        for refused in ("no-go", "insufficient-samples", "nonpass"):
            self.assertFalse(_passed("measure", {"status": refused}), refused)

    def test_success_phases_require_true_success(self) -> None:
        for phase in ("candidates", "selection-pressure"):
            self.assertTrue(_passed(phase, {"success": True}), phase)
            self.assertFalse(_passed(phase, {"success": False}), phase)
            self.assertFalse(_passed(phase, {}), phase)


class PartialCollectionTests(unittest.TestCase):
    def test_observed_partial_passes_without_a_success_flag(self) -> None:
        for phase in ("lifecycle", "nested", "faults"):
            self.assertTrue(_passed(phase, _partial("observed-partial")), phase)

    def test_other_states_never_pass(self) -> None:
        for phase in ("lifecycle", "nested", "faults"):
            for status in ("nonpass", "in-progress", "incomplete"):
                self.assertFalse(_passed(phase, _partial(status)), f"{phase} {status}")
            self.assertFalse(_passed(phase, {"success": True}), phase)

    def test_every_phase_outside_the_races_has_a_rule(self) -> None:
        for phase in rl00bc_driver.PHASES:
            if phase not in rl00bc_outside.RACES:
                self.assertFalse(_passed(phase, {}), phase)


class AdoptionVerdictTests(unittest.TestCase):
    def test_phase_names_match_the_producer(self) -> None:
        self.assertEqual(rl00bc_driver.ADOPTION_FINAL_PHASE, _FINAL)
        self.assertEqual(rl00bc_driver.ADOPTION_UNRUN_PROOF, rl00bc_adoption.UNRUN_PROOF)

    def test_finished_chain_passes_despite_the_unrun_proof(self) -> None:
        self.assertTrue(_passed("adoption", _chain("clone-template", "export-old", _FINAL)))

    def test_chain_that_stopped_before_its_final_phase_fails(self) -> None:
        self.assertFalse(_passed("adoption", _chain("clone-template", "export-old")))

    def test_unrun_or_failed_final_phase_fails(self) -> None:
        unrun = {"status": "unrun"}
        for final in (unrun, _native(success=False), _native(cleanup=False)):
            result = _chain("clone-template", _FINAL)
            _phases(result)[_FINAL] = final
            self.assertFalse(_passed("adoption", result), final)
        only_unrun: dict[str, object] = {
            "phases": {_FINAL: unrun, rl00bc_adoption.UNRUN_PROOF: unrun}
        }
        self.assertFalse(_passed("adoption", only_unrun))

    def test_only_the_delegation_proof_may_be_unrun(self) -> None:
        result = _chain("clone-template", _FINAL)
        _phases(result)["clone-template"] = {"status": "unrun"}
        self.assertFalse(_passed("adoption", result))

    def test_failed_phase_fails_the_chain(self) -> None:
        result = _chain("clone-template", _FINAL)
        _phases(result)["clone-template"] = _native(success=False)
        self.assertFalse(_passed("adoption", result))

    def test_incomplete_cleanup_fails_the_chain(self) -> None:
        result = _chain("clone-template", _FINAL)
        _phases(result)["clone-template"] = _native(cleanup=False)
        self.assertFalse(_passed("adoption", result))

    def test_phase_record_with_an_error_fails_the_chain(self) -> None:
        result = _chain("clone-template", _FINAL)
        _phases(result)["export-old"] = {"argv": [], "cwd": "/scratch", "error": "RuntimeError: x"}
        self.assertFalse(_passed("adoption", result))

    def test_unexpected_shapes_fail(self) -> None:
        shapes: list[dict[str, object]] = [
            {},
            {"phases": None},
            {"phases": []},
            {"phases": [_native()]},
            {"phases": {_FINAL: "success"}},
        ]
        for shape in shapes:
            self.assertFalse(_passed("adoption", shape), shape)


if __name__ == "__main__":
    unittest.main()
