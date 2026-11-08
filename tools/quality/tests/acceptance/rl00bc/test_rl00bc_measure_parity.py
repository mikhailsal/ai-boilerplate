"""Remote report-level regressions for RL00c native timing parity."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from typing import cast

from tests.acceptance.rl00bc import rl00bc_corpus, rl00bc_measure_parity


def _record(profile: str, root: Path, *, native_id_start: int = 1) -> dict[str, object]:
    cases = rl00bc_corpus.expected(profile, "small")
    rows: list[dict[str, object]] = [
        {
            "id": case.identity,
            "variant": case.variant,
            "outcome": "passed",
            "source": str(root / "test" / "native_test"),
            "native_id": native_id_start + index,
        }
        for index, case in enumerate(cases)
    ]
    return {
        "corpus_root": str(root),
        "native_cases": rows,
        "kernel": {"native_status": 0, "cleanup_complete": True},
    }


def _strict(case: rl00bc_corpus.Case, root: Path, *, native_id: int = 73) -> dict[str, object]:
    return {
        "corpus_root": str(root),
        "native_cases": [
            {
                "id": case.identity,
                "variant": case.variant,
                "outcome": "passed",
                "source": str(root / "test" / "native_test"),
                "native_id": native_id,
            }
        ],
        "kernel": {"native_status": 0, "cleanup_complete": True},
    }


class TimingNativeParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.baseline_root = self.root / "baseline"
        self.strict_root = self.root / "strict"

    def test_complete_preregistered_corpus_and_fresh_source_roots_match(self) -> None:
        baseline = _record("python", self.baseline_root)
        case = rl00bc_corpus.expected("python", "small")[0]
        strict = _strict(case, self.strict_root, native_id=999)
        evidence = rl00bc_measure_parity.canonical("python", "small", baseline)
        self.assertEqual(len(cast(list[object], evidence["rows"])), 4)
        result = rl00bc_measure_parity.selected(case, baseline, strict)
        self.assertEqual(result["native_status"], 0)
        row = cast(dict[str, object], result["row"])
        self.assertEqual(row["source"], "test/native_test")
        self.assertEqual(row["source_state"], "native-source-observed")

    def test_same_variant_with_wrong_native_id_is_rejected(self) -> None:
        for profile in ("python", "php"):
            with self.subTest(profile=profile):
                baseline = _record(profile, self.baseline_root)
                case = rl00bc_corpus.expected(profile, "small")[0]
                strict = _strict(case, self.strict_root)
                rows = cast(list[dict[str, object]], strict["native_cases"])
                rows[0]["id"] = "different native case"
                self.assertEqual(rows[0]["variant"], case.variant)
                with self.assertRaises(ValueError):
                    rl00bc_measure_parity.selected(case, baseline, strict)

    def test_changed_native_outcome_is_rejected(self) -> None:
        baseline = _record("python", self.baseline_root)
        case = rl00bc_corpus.expected("python", "small")[0]
        strict = _strict(case, self.strict_root)
        cast(list[dict[str, object]], strict["native_cases"])[0]["outcome"] = "skipped"
        with self.assertRaises(ValueError):
            rl00bc_measure_parity.selected(case, baseline, strict)

    def test_changed_actual_source_is_rejected(self) -> None:
        baseline = _record("python", self.baseline_root)
        case = rl00bc_corpus.expected("python", "small")[0]
        strict = _strict(case, self.strict_root)
        cast(list[dict[str, object]], strict["native_cases"])[0]["source"] = str(
            self.strict_root / "test" / "other_test"
        )
        with self.assertRaises(ValueError):
            rl00bc_measure_parity.selected(case, baseline, strict)

    def test_nonzero_exit_and_incomplete_cleanup_are_rejected(self) -> None:
        for kernel in (
            {"native_status": 1, "cleanup_complete": True},
            {"native_status": 0, "cleanup_complete": False},
        ):
            with self.subTest(kernel=kernel):
                baseline = _record("python", self.baseline_root)
                baseline["kernel"] = kernel
                with self.assertRaises(ValueError):
                    rl00bc_measure_parity.canonical("python", "small", baseline)
                case = rl00bc_corpus.expected("python", "small")[0]
                strict = _strict(case, self.strict_root)
                with self.assertRaises(ValueError):
                    rl00bc_measure_parity.selected(case, baseline, strict)
                baseline["kernel"] = {"native_status": 0, "cleanup_complete": True}
                strict["kernel"] = kernel
                with self.assertRaises(ValueError):
                    rl00bc_measure_parity.selected(case, baseline, strict)

    def test_corresponding_canonical_evidence_matches_across_roots(self) -> None:
        first = rl00bc_measure_parity.canonical(
            "python", "small", _record("python", self.baseline_root)
        )
        second = rl00bc_measure_parity.canonical(
            "python", "small", _record("python", self.strict_root, native_id_start=100)
        )
        result = rl00bc_measure_parity.paired(
            {"canonical_evidence": first}, {"canonical_evidence": second}
        )
        self.assertIs(result["matched"], True)

    def test_paired_changed_identity_outcome_source_or_exit_is_rejected(self) -> None:
        original = rl00bc_measure_parity.canonical("python", "small", _record("python", self.root))
        for field, changed in (
            ("id", "other"),
            ("outcome", "skipped"),
            ("source", "test/other_test"),
        ):
            with self.subTest(field=field):
                other = copy.deepcopy(original)
                cast(list[dict[str, object]], other["rows"])[0][field] = changed
                with self.assertRaises(ValueError):
                    rl00bc_measure_parity.paired(
                        {"canonical_evidence": original}, {"canonical_evidence": other}
                    )
        other = copy.deepcopy(original)
        other["native_status"] = 1
        with self.assertRaises(ValueError):
            rl00bc_measure_parity.paired(
                {"canonical_evidence": original}, {"canonical_evidence": other}
            )

    def test_missing_or_malformed_canonical_evidence_is_rejected(self) -> None:
        malformed_values: tuple[object, ...] = (
            None, {}, [], "not-evidence", {"rows": [], "native_status": 0}
        )
        for malformed in malformed_values:
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                rl00bc_measure_parity.paired(
                    {"canonical_evidence": malformed}, {"canonical_evidence": malformed}
                )


if __name__ == "__main__":
    unittest.main()
