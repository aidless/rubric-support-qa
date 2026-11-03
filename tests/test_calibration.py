import json
import math
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from calibration.agreement import (binary_consistency, continuous_consistency,
                                  fleiss_kappa, kappa, pearson, spearman)
from calibration.drift import (check_drift, compute_fnr_fpr,
                               consecutive_drift_state, load_baseline)
from calibration.intervals import ci_width, wilson_interval


class KappaTests(unittest.TestCase):
    def test_perfect_agreement_is_one(self):
        self.assertAlmostEqual(kappa(10, 0, 0, 10), 1.0)

    def test_known_value(self):
        # 60% 一致、期望一致 50% → κ = 0.2
        self.assertAlmostEqual(kappa(30, 20, 20, 30), 0.2)

    def test_zero_total_is_nan(self):
        self.assertTrue(math.isnan(kappa(0, 0, 0, 0)))

    def test_single_cell_is_nan(self):
        # 所有人都判同一类：po=1 且 pe=1，κ 无定义
        self.assertTrue(math.isnan(kappa(10, 0, 0, 0)))


class CorrelationTests(unittest.TestCase):
    def test_pearson_perfect(self):
        self.assertAlmostEqual(pearson([1, 2, 3], [2, 4, 6]), 1.0)

    def test_pearson_negative(self):
        self.assertAlmostEqual(pearson([1, 2, 3], [6, 4, 2]), -1.0)

    def test_pearson_zero_variance_is_nan(self):
        self.assertTrue(math.isnan(pearson([1, 1, 1], [1, 2, 3])))

    def test_spearman_with_ties(self):
        # x 秩 1,2.5,2.5 ; y 秩 1,2,3 → ρ = 0.8660
        rho = spearman([1, 2, 2], [1, 2, 3])
        self.assertAlmostEqual(rho, 0.866, places=3)


class BinaryConsistencyTests(unittest.TestCase):
    def test_gate_pass_on_strong_agreement(self):
        res = binary_consistency([1, 1, 1, 0, 0, 0], [1, 1, 1, 0, 0, 1])
        self.assertEqual(res["gate"], "PASS")
        self.assertEqual(res["confusion"]["tp"], 3)
        self.assertEqual(res["confusion"]["fn"], 0)
        self.assertEqual(res["confusion"]["fp"], 1)

    def test_gate_fail_when_judge_always_says_one(self):
        res = binary_consistency([0, 0, 1, 0], [1, 1, 1, 1])
        self.assertEqual(res["gate"], "FAIL")
        self.assertAlmostEqual(res["judge_fpr_vs_human"], 1.0)

    def test_fnr_fpr_math(self):
        res = binary_consistency([1, 1, 1, 1, 0, 0, 0, 0], [1, 1, 0, 0, 0, 0, 1, 0])
        self.assertAlmostEqual(res["judge_fnr_vs_human"], 0.5)
        self.assertAlmostEqual(res["judge_fpr_vs_human"], 0.25)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            binary_consistency([1, 0], [1])


class ContinuousConsistencyTests(unittest.TestCase):
    def test_identical_scores_pass(self):
        res = continuous_consistency([1, 2, 3, 4], [1, 2, 3, 4])
        self.assertEqual(res["gate"], "PASS")
        self.assertAlmostEqual(res["mean_offset"], 0.0)
        self.assertAlmostEqual(res["spearman_rho"], 1.0)

    def test_constant_offset_above_gate(self):
        res = continuous_consistency([1, 2, 3], [2, 3, 4])
        self.assertEqual(res["gate"], "FAIL")
        self.assertAlmostEqual(res["mean_offset"], 1.0)


class FleissTests(unittest.TestCase):
    def test_perfect_split_agreement(self):
        # 3 样本 3 评分者全一致，类别各半 → κ = 1
        self.assertAlmostEqual(fleiss_kappa([[3, 0], [0, 3], [3, 0]]), 1.0)

    def test_hand_computed_value(self):
        # 见 handoff：P_bar=7/9, P_e=41/81 → κ = 0.55
        self.assertAlmostEqual(fleiss_kappa([[3, 0], [0, 3], [2, 1]]), 0.55)

    def test_all_same_category_is_nan(self):
        self.assertTrue(math.isnan(fleiss_kappa([[3, 0], [3, 0]])))

    def test_inconsistent_raters_raise(self):
        with self.assertRaises(ValueError):
            fleiss_kappa([[3, 0], [2, 0]])


class DriftTests(unittest.TestCase):
    def test_compute_fnr_fpr(self):
        verdicts = [
            {"gold": 1, "judge_label": 1}, {"gold": 1, "judge_label": 0},
            {"gold": 0, "judge_label": 0}, {"gold": 0, "judge_label": 1},
        ]
        res = compute_fnr_fpr(verdicts)
        self.assertEqual((res["tp"], res["fn"], res["tn"], res["fp"]), (1, 1, 1, 1))
        self.assertAlmostEqual(res["fnr"], 0.5)
        self.assertAlmostEqual(res["fpr"], 0.5)

    def test_stable_when_identical(self):
        base = {"fnr": 0.1, "fpr": 0.05}
        drift = check_drift(base, base)
        self.assertEqual(drift["verdict"], "STABLE")
        self.assertFalse(drift["drifted"])

    def test_fnr_drift_detected(self):
        drift = check_drift({"fnr": 0.2, "fpr": 0.05}, {"fnr": 0.1, "fpr": 0.05})
        self.assertEqual(drift["verdict"], "DRIFT_DETECTED")
        self.assertAlmostEqual(drift["delta_fnr"], 0.1)

    def test_fpr_drift_detected(self):
        drift = check_drift({"fnr": 0.1, "fpr": 0.12}, {"fnr": 0.1, "fpr": 0.05})
        self.assertTrue(drift["drifted"])

    def test_threshold_boundary_is_not_drift(self):
        drift = check_drift({"fnr": 0.15, "fpr": 0.05}, {"fnr": 0.10, "fpr": 0.05})
        self.assertFalse(drift["drifted"])

    def test_consecutive_state(self):
        hit = {"drifted": True}
        miss = {"drifted": False}
        self.assertEqual(consecutive_drift_state([miss]), "STABLE")
        self.assertEqual(consecutive_drift_state([miss, hit]), "DRIFT_DETECTED")
        self.assertEqual(consecutive_drift_state([hit, hit]), "UNCALIBRATED")
        self.assertEqual(consecutive_drift_state([hit, miss]), "STABLE")

    def test_load_baseline_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "calibration.json"
            path.write_text(json.dumps({"fnr": 0.08, "fpr": 0.03,
                                        "n_gold": 24, "prompt_version": "v2"}),
                            encoding="utf-8")
            base = load_baseline(path)
            self.assertAlmostEqual(base["fnr"], 0.08)
            self.assertEqual(base["n_gold"], 24)
            self.assertEqual(base["prompt_version"], "v2")


class WilsonTests(unittest.TestCase):
    def test_interval_contains_point_estimate(self):
        low, high = wilson_interval(80, 100)
        self.assertLess(low, 0.8)
        self.assertGreater(high, 0.8)

    def test_zero_n_is_full_range(self):
        self.assertEqual(wilson_interval(0, 0), (0.0, 1.0))

    def test_width_shrinks_with_n(self):
        self.assertLess(ci_width(800, 1000), ci_width(80, 100))

    def test_known_value(self):
        low, high = wilson_interval(300, 400)
        self.assertAlmostEqual(low, 0.7053, places=3)
        self.assertAlmostEqual(high, 0.7899, places=3)


if __name__ == "__main__":
    unittest.main()
