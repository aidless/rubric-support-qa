import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import make_disagreement as poolgen  # noqa: E402

DATA = ROOT / "data"


def load(path: pathlib.Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class PoolShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_items = load(DATA / "test.frozen.jsonl")
        cls.pool = load(DATA / "disagreement.pool.jsonl")

    def test_exactly_120_and_30_per_type(self):
        self.assertEqual(len(self.pool), 120)
        counts = {}
        for row in self.pool:
            counts[row["d_type"]] = counts.get(row["d_type"], 0) + 1
        self.assertEqual(counts, {"D1": 30, "D2": 30, "D3": 30, "D4": 30})

    def test_self_check_passes(self):
        self.assertEqual(poolgen.check_pool(self.pool, self.test_items), [])

    def test_no_human_labels_and_not_measured(self):
        for row in self.pool:
            self.assertIsNone(row["human_label"])
            self.assertEqual(row["label_status"], "unlabeled")
            self.assertEqual(row["verdict_status"], "constructed")
            self.assertFalse(row["measured"])

    def test_verdict_pairs_match_preregistration(self):
        expected = {"D1": ("pass", "fail"), "D2": ("pass", "fail"),
                    "D3": ("fail", "pass"), "D4": ("pass", "fail")}
        for row in self.pool:
            self.assertEqual((row["bench_verdict"], row["rubric_verdict"]),
                             expected[row["d_type"]], row["id"])

    def test_source_items_are_frozen_test_items(self):
        by_id = {row["id"]: row for row in self.test_items}
        for row in self.pool:
            source = by_id[row["source_item_id"]]
            self.assertEqual(source["split"], "test")
            self.assertEqual(source["question"], row["question"])

    def test_candidate_answers_unique(self):
        answers = [row["candidate_answer"] for row in self.pool]
        self.assertEqual(len(set(answers)), len(answers))


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = load(DATA / "disagreement.pool.jsonl")

    def test_gold_spans_exist_in_context(self):
        for row in self.pool:
            for span in row["evidence"]["rubric_gold_spans"]:
                doc = next((c for c in row["context"] if c["doc_id"] == span["doc_id"]), None)
                self.assertIsNotNone(doc, row["id"])
                self.assertIn(span["span"], doc["text"], row["id"])

    def test_d2_assertions_are_outside_context(self):
        for row in self.pool:
            if row["d_type"] != "D2":
                continue
            assertion = row["evidence"]["unsourced_assertion"]
            self.assertIn(assertion, row["candidate_answer"])
            for doc in row["context"]:
                self.assertNotIn(assertion, doc["text"], row["id"])

    def test_d3_is_grounded_paraphrase(self):
        for row in self.pool:
            if row["d_type"] != "D3":
                continue
            self.assertIsNone(row["evidence"]["unsourced_assertion"])
            self.assertEqual(row["rubric_basis"], "L2.complete")

    def test_file_matches_regeneration(self):
        pool = poolgen.build_pool(load(DATA / "test.frozen.jsonl"))
        rendered = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in pool
        )
        self.assertEqual(rendered, (DATA / "disagreement.pool.jsonl").read_text(encoding="utf-8"))

    def test_bad_pool_is_rejected(self):
        pool = poolgen.build_pool(load(DATA / "test.frozen.jsonl"))
        pool[0]["human_label"] = "pass"
        errors = poolgen.check_pool(pool, load(DATA / "test.frozen.jsonl"))
        self.assertTrue(any("构造池不得带人工标签" in err for err in errors))


if __name__ == "__main__":
    unittest.main()
