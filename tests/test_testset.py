import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import make_dev as dev  # noqa: E402
import make_test as testgen  # noqa: E402
import freeze_test as freezer  # noqa: E402

DATA = ROOT / "data"


def load(path: pathlib.Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class ShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = load(DATA / "test.frozen.jsonl")
        cls.dev_items = load(DATA / "dev.frozen.jsonl")

    def test_exactly_800_rows(self):
        self.assertEqual(len(self.items), 800)

    def test_kind_counts(self):
        kinds = {}
        for row in self.items:
            kind = row["source"]["kind"]
            kinds[kind] = kinds.get(kind, 0) + 1
        self.assertEqual(kinds, {"synthetic_boundary": 600,
                                 "real_derived_paraphrase": 100,
                                 "adversarial_injection": 100})

    def test_boundary_family_domain_shape(self):
        for family in dev.FAMILIES:
            subset = [row for row in self.items
                      if row["source"]["kind"] == "synthetic_boundary"
                      and row["family"] == family]
            self.assertEqual(len(subset), 120, family)
            per_domain = {}
            for row in subset:
                per_domain[row["domain"]] = per_domain.get(row["domain"], 0) + 1
            self.assertEqual(len(per_domain), 10, family)
            for domain, count in per_domain.items():
                self.assertEqual(count, 12, f"{family}/{domain}")

    def test_all_split_test_and_ids_unique(self):
        self.assertEqual({row["split"] for row in self.items}, {"test"})
        self.assertEqual(len({row["id"] for row in self.items}), 800)
        self.assertEqual(len({row["question"] for row in self.items}), 800)

    def test_no_dev_overlap(self):
        self.assertEqual(freezer.content_check(self.items, self.dev_items), [])

    def test_frozen_bytes_identical(self):
        self.assertEqual((DATA / "test.jsonl").read_bytes(),
                         (DATA / "test.frozen.jsonl").read_bytes())


class ReproduceTests(unittest.TestCase):
    def test_build_is_deterministic(self):
        first = testgen.build_items(testgen.TEST_SEED)
        second = testgen.build_items(testgen.TEST_SEED)
        self.assertEqual(first, second)

    def test_generated_matches_frozen(self):
        items = testgen.build_items(testgen.TEST_SEED)
        rendered = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in items
        )
        self.assertEqual(rendered, (DATA / "test.jsonl").read_text(encoding="utf-8"))

    def test_wrong_seed_rejected(self):
        with self.assertRaises(ValueError):
            testgen.build_items(20261103)


class ManifestTests(unittest.TestCase):
    def test_manifest_check_passes(self):
        items = load(DATA / "test.jsonl")
        self.assertEqual(freezer.check_manifest(items), [])

    def test_manifest_records_three_files(self):
        manifest = json.loads((DATA / "manifest.test.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["files"]),
                         {"data/test.jsonl", "data/test.frozen.jsonl", "data/dev.frozen.jsonl"})
        self.assertEqual(manifest["dataset"]["n"], 800)
        self.assertEqual(manifest["dataset"]["dev_overlap"], 0)


if __name__ == "__main__":
    unittest.main()
