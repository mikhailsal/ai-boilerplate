"""Remote regressions for unavailable and sampled resource observations."""

from __future__ import annotations

import unittest

from tests.acceptance.rl00bc import rl00bc_measure_metrics


class SampledResourceTests(unittest.TestCase):
    def test_exact_memory_peak_needs_no_sampling(self) -> None:
        record: dict[str, object] = {
            "kernel": {"memory_peak_bytes": 42, "resource_sample_count": 0}
        }
        self.assertEqual(rl00bc_measure_metrics.memory(record), (42.0, "kernel-peak"))

    def test_sampled_zero_remains_a_real_lower_bound(self) -> None:
        record: dict[str, object] = {
            "kernel": {
                "memory_peak_bytes": None,
                "sampled_memory_peak_bytes": 0,
                "max_tasks": 0,
                "resource_sample_count": 1,
            }
        }
        self.assertEqual(rl00bc_measure_metrics.memory(record), (0.0, "sampled-lower-bound"))
        self.assertEqual(rl00bc_measure_metrics.tasks(record), (0.0, "sampled-lower-bound"))

    def test_unobserved_values_never_become_zero(self) -> None:
        for count in (None, 0, False):
            record: dict[str, object] = {
                "kernel": {
                    "memory_peak_bytes": None,
                    "sampled_memory_peak_bytes": None,
                    "max_tasks": None,
                    "resource_sample_count": count,
                }
            }
            with self.assertRaises(ValueError, msg=f"memory, count {count!r}"):
                rl00bc_measure_metrics.memory(record)
            with self.assertRaises(ValueError, msg=f"tasks, count {count!r}"):
                rl00bc_measure_metrics.tasks(record)

    def test_sample_count_cannot_make_missing_values_available(self) -> None:
        record: dict[str, object] = {
            "kernel": {
                "memory_peak_bytes": None,
                "sampled_memory_peak_bytes": None,
                "max_tasks": None,
                "resource_sample_count": 1,
            }
        }
        with self.assertRaises(TypeError):
            rl00bc_measure_metrics.memory(record)
        with self.assertRaises(TypeError):
            rl00bc_measure_metrics.tasks(record)

    def test_exact_and_sampled_memory_keep_distinct_kinds(self) -> None:
        exact: dict[str, object] = {
            "kernel": {
                "memory_peak_bytes": 800,
                "sampled_memory_peak_bytes": 400,
                "max_tasks": 3,
                "resource_sample_count": 2,
            }
        }
        sampled: dict[str, object] = {
            "kernel": {
                "memory_peak_bytes": None,
                "sampled_memory_peak_bytes": 400,
                "max_tasks": 3,
                "resource_sample_count": 2,
            }
        }
        self.assertEqual(rl00bc_measure_metrics.memory(exact), (800.0, "kernel-peak"))
        self.assertEqual(rl00bc_measure_metrics.memory(sampled), (400.0, "sampled-lower-bound"))
        self.assertEqual(rl00bc_measure_metrics.tasks(exact), (3.0, "sampled-lower-bound"))

    def test_distributions_do_not_mix_exact_peaks_and_lower_bounds(self) -> None:
        observations: dict[str, list[dict[str, object]]] = {
            "native": [
                {"max_leaf_memory_peak_bytes": 800, "max_leaf_memory_peak_kind": "kernel-peak"},
                {
                    "max_leaf_memory_peak_bytes": 400,
                    "max_leaf_memory_peak_kind": "sampled-lower-bound",
                },
            ]
        }
        result = rl00bc_measure_metrics.distributions(observations, ("max_leaf_memory_peak_bytes",))
        self.assertEqual(
            result,
            {
                "native": {
                    "max_leaf_memory_peak_bytes": {
                        "by_kind": {
                            "kernel-peak": {"samples": 1, "p50": 800.0, "p95": 800.0},
                            "sampled-lower-bound": {"samples": 1, "p50": 400.0, "p95": 400.0},
                        }
                    }
                }
            },
        )

    def test_unknown_distribution_kind_is_not_an_exact_peak(self) -> None:
        observations: dict[str, list[dict[str, object]]] = {
            "native": [
                {"max_leaf_memory_peak_bytes": 800},
            ]
        }
        with self.assertRaises(ValueError):
            rl00bc_measure_metrics.distributions(observations, ("max_leaf_memory_peak_bytes",))


if __name__ == "__main__":
    unittest.main()
