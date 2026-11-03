import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from rubric.lint import lint_files, lint_rubric  # noqa: E402

RUBRIC_PATH = ROOT / "rubric" / "rubric.v0.yaml"
CE_PATH = ROOT / "rubric" / "counterexamples.jsonl"


def load_rubric() -> dict:
    return yaml.safe_load(RUBRIC_PATH.read_text(encoding="utf-8"))


def load_ce() -> list[dict]:
    rows = []
    for line in CE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


class ValidRubricTests(unittest.TestCase):
    def test_shipped_rubric_passes_lint(self):
        self.assertEqual(lint_files(RUBRIC_PATH, CE_PATH), [])

    def test_every_l1_item_has_two_counterexamples(self):
        rubric = load_rubric()
        ces = load_ce()
        by_l1 = {}
        for ce in ces:
            by_l1.setdefault(ce["l1_id"], []).append(ce["ce_id"])
        for item in rubric["levels"]["L1"]["items"]:
            self.assertGreaterEqual(len(by_l1.get(item["id"], [])), 2, item["id"])

    def test_threshold_is_reachable_but_not_free(self):
        rubric = load_rubric()
        l2 = rubric["levels"]["L2"]
        self.assertGreater(l2["pass_threshold"], 0)
        self.assertLessEqual(l2["pass_threshold"], 2.0)


class WeightTests(unittest.TestCase):
    def test_weight_sum_not_one(self):
        rubric = load_rubric()
        rubric["levels"]["L2"]["items"][0]["weight"] = 0.31
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R2" in error for error in errors))

    def test_zero_weight_rejected(self):
        rubric = load_rubric()
        rubric["levels"]["L2"]["items"][0]["weight"] = 0.0
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R2" in error for error in errors))

    def test_unreachable_threshold(self):
        rubric = load_rubric()
        rubric["levels"]["L2"]["pass_threshold"] = 2.5
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R3" in error for error in errors))

    def test_missing_threshold(self):
        rubric = load_rubric()
        del rubric["levels"]["L2"]["pass_threshold"]
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R3" in error for error in errors))


class CounterexampleTests(unittest.TestCase):
    def test_referenced_counterexample_missing(self):
        rubric = load_rubric()
        rubric["levels"]["L1"]["items"][0]["counterexamples"] = ["CE-NOT-EXIST"]
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R4" in error for error in errors))

    def test_l1_item_without_counterexample(self):
        rubric = load_rubric()
        rubric["levels"]["L1"]["items"][0]["counterexamples"] = []
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("没有反例" in error for error in errors))

    def test_counterexample_points_to_unknown_l1(self):
        rubric = load_rubric()
        ces = copy.deepcopy(load_ce())
        ces[0]["l1_id"] = "L1.unknown"
        errors = lint_rubric(rubric, ces)
        self.assertTrue(any("R5" in error for error in errors))

    def test_counterexample_missing_why_fail(self):
        rubric = load_rubric()
        ces = copy.deepcopy(load_ce())
        ces[0]["why_fail"] = ""
        errors = lint_rubric(rubric, ces)
        self.assertTrue(any("R5" in error for error in errors))

    def test_duplicate_counterexample_id(self):
        rubric = load_rubric()
        ces = copy.deepcopy(load_ce())
        ces.append(copy.deepcopy(ces[0]))
        errors = lint_rubric(rubric, ces)
        self.assertTrue(any("重复" in error for error in errors))


class DimensionTests(unittest.TestCase):
    def test_missing_distinguishes_from(self):
        rubric = load_rubric()
        rubric["levels"]["L2"]["items"][0]["distinguishes_from"] = []
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R6" in error for error in errors))

    def test_duplicate_dimension_id(self):
        rubric = load_rubric()
        rubric["levels"]["L2"]["items"][1]["id"] = rubric["levels"]["L2"]["items"][0]["id"]
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R6" in error for error in errors))

    def test_missing_definition(self):
        rubric = load_rubric()
        rubric["levels"]["L2"]["items"][0]["definition"] = ""
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R6" in error for error in errors))


class FailClosedTests(unittest.TestCase):
    def test_evidence_gap_must_be_review(self):
        rubric = load_rubric()
        rubric["levels"]["L3"]["evidence_gap_verdict"] = "PASS"
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R8" in error for error in errors))

    def test_l1_evidence_required(self):
        rubric = load_rubric()
        rubric["levels"]["L1"]["items"][0]["evidence_required"] = False
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R7" in error for error in errors))

    def test_cross_version_compare_must_be_false(self):
        rubric = load_rubric()
        rubric["conflict_policy"]["cross_version_compare"] = True
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R12" in error for error in errors))

    def test_tie_break_must_be_fail_closed(self):
        rubric = load_rubric()
        rubric["conflict_policy"]["tie_break"] = "average"
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R9" in error for error in errors))


class PolicyTests(unittest.TestCase):
    def test_priority_not_in_precedence(self):
        rubric = load_rubric()
        rubric["levels"]["L1"]["items"][0]["priority"] = "growth"
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R9" in error for error in errors))

    def test_priority_map_key_mismatch(self):
        rubric = load_rubric()
        rubric["conflict_policy"]["l1_priority_map"].pop("L1.pii")
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R10" in error for error in errors))

    def test_empty_authority_whitelist(self):
        rubric = load_rubric()
        rubric["authority_whitelist"] = []
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R11" in error for error in errors))

    def test_whitelist_entry_missing_scope(self):
        rubric = load_rubric()
        rubric["authority_whitelist"][0]["scope"] = ""
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R11" in error for error in errors))

    def test_bad_schema_version(self):
        rubric = load_rubric()
        rubric["schema_version"] = 2
        errors = lint_rubric(rubric, load_ce())
        self.assertTrue(any("R1" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
