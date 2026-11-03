import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.freeze import content_check, read_jsonl  # noqa: E402
from scripts.make_dev import (FAMILIES, PER_FAMILY, content_sha256,  # noqa: E402
                             normalize, write_jsonl, build_items)

DATA = ROOT / "data"


def load_dev() -> list[dict]:
    return read_jsonl(DATA / "dev.jsonl")


class ShapeTests(unittest.TestCase):
    def test_exactly_300_rows(self):
        self.assertEqual(len(load_dev()), PER_FAMILY * len(FAMILIES))

    def test_each_family_has_60(self):
        rows = load_dev()
        for family in FAMILIES:
            self.assertEqual(sum(1 for r in rows if r["family"] == family), PER_FAMILY, family)

    def test_each_family_covers_10_domains_x_6_questions(self):
        rows = load_dev()
        for family in FAMILIES:
            subset = [r for r in rows if r["family"] == family]
            per_domain = {}
            for row in subset:
                per_domain[row["domain"]] = per_domain.get(row["domain"], 0) + 1
            self.assertEqual(len(per_domain), 10, family)
            for domain, count in per_domain.items():
                self.assertEqual(count, 6, f"{family}/{domain}")
            # 同域内 6 条问句必须互不相同
            by_domain = {}
            for row in subset:
                by_domain.setdefault(row["domain"], set()).add(normalize(row["question"]))
            for domain, questions in by_domain.items():
                self.assertEqual(len(questions), 6, f"{family}/{domain} 问句重复")

    def test_ids_and_questions_unique(self):
        rows = load_dev()
        self.assertEqual(len({r["id"] for r in rows}), len(rows))
        self.assertEqual(len({normalize(r["question"]) for r in rows}), len(rows))


class ContentTests(unittest.TestCase):
    def test_content_sha_matches(self):
        for row in load_dev():
            self.assertEqual(content_sha256(row["question"], row["context"]),
                             row["content_sha256"], row["id"])

    def test_gold_spans_exist_in_context(self):
        for row in load_dev():
            docs = {doc["doc_id"]: doc for doc in row["context"]}
            for span in row["reference"]["gold_spans"]:
                self.assertIn(span["doc_id"], docs, row["id"])
                self.assertIn(span["span"], docs[span["doc_id"]]["text"], row["id"])

    def test_effective_range_not_inverted(self):
        for row in load_dev():
            for doc in row["context"]:
                if doc["effective_from"] and doc["effective_to"]:
                    self.assertLessEqual(doc["effective_from"], doc["effective_to"], doc["doc_id"])

    def test_stale_rows_have_expired_doc_and_notice(self):
        for row in load_dev():
            if row["family"] != "stale":
                continue
            docs = {doc["doc_id"]: doc for doc in row["context"]}
            self.assertIn("KB-VER-001", docs)
            self.assertTrue(any(doc["effective_to"] for doc in docs.values()))

    def test_overreach_rows_have_authority_whitelist_doc(self):
        for row in load_dev():
            if row["family"] == "overreach":
                self.assertIn("KB-AUTH-001", {doc["doc_id"] for doc in row["context"]})

    def test_unanswerable_rows_stress_must_refuse(self):
        for row in load_dev():
            if row["family"] == "unanswerable":
                self.assertIn("L1.must_refuse", row["stress"])

    def test_reference_labels_match_family(self):
        expected = {
            "unanswerable": "refuse",
            "multi_hop": "answer_grounded",
            "stale": "disclose_stale",
            "conflict": "escalate",
            "overreach": "deny_overreach",
        }
        for row in load_dev():
            self.assertEqual(row["reference"]["label"], expected[row["family"]], row["id"])

    def test_source_is_declared_synthetic(self):
        for row in load_dev():
            self.assertEqual(row["source"]["kind"], "synthetic_template", row["id"])
            self.assertEqual(row["source"]["seed"], 20261103)

    def test_content_check_accepts_shipped_data(self):
        self.assertEqual(content_check(load_dev()), [])


class FreezeTests(unittest.TestCase):
    def test_frozen_is_byte_identical(self):
        self.assertEqual((DATA / "dev.frozen.jsonl").read_bytes(), (DATA / "dev.jsonl").read_bytes())

    def test_manifest_hashes_match_files(self):
        manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
        for rel, info in manifest["files"].items():
            path = ROOT / rel
            import hashlib
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             info["sha256"], rel)

    def test_manifest_metadata(self):
        manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["dataset"]["n"], 300)
        self.assertEqual(manifest["dataset"]["split"], "dev")
        self.assertEqual(set(manifest["dataset"]["families"]), set(FAMILIES))
        for count in manifest["dataset"]["families"].values():
            self.assertEqual(count, PER_FAMILY)
        self.assertIn("data/dev.jsonl", manifest["files"])
        self.assertIn("rubric/rubric.v0.yaml", manifest["files"])
        self.assertIn("prereg.md", manifest["files"])

    def test_prereg_covers_h1_to_h4(self):
        text = (ROOT / "prereg.md").read_text(encoding="utf-8")
        for hyp in ("H1", "H2", "H3", "H4"):
            self.assertIn(hyp, text)
        self.assertIn("未检验", text)


class ReproduceTests(unittest.TestCase):
    def test_regeneration_is_byte_identical(self):
        items = build_items(20261103)
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "dev.jsonl"
            write_jsonl(out, items)
            self.assertEqual(out.read_bytes(), (DATA / "dev.jsonl").read_bytes())

    def test_generation_order_is_stable_across_calls(self):
        first = [row["id"] for row in build_items(20261103)]
        second = [row["id"] for row in build_items(20261103)]
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first))

    def test_unknown_seed_is_refused(self):
        with self.assertRaises(ValueError):
            build_items(20261104)


if __name__ == "__main__":
    unittest.main()
