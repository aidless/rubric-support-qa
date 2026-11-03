import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from scripts.check_requirements import (  # noqa: E402
    AUTHOR_HEADING,
    CONSTRAINT_HEADING,
    check_requirements,
    section_rows,
)

RUBRIC_PATH = ROOT / "rubric" / "rubric.v0.yaml"
REQ_PATH = ROOT / "requirements.md"

MINI_RUBRIC = {
    "levels": {
        "L1": {
            "items": [
                {"id": "L1.pii"},
                {"id": "L1.grounding"},
                {"id": "L1.authority"},
                {"id": "L1.must_refuse"},
            ]
        },
        "L2": {
            "items": [
                {"id": "L2.complete"},
                {"id": "L2.faithful"},
                {"id": "L2.compliance"},
                {"id": "L2.actionable"},
                {"id": "L2.clarity"},
            ]
        },
    }
}

HEADER = (
    "| ID | 项目 | 硬约束 | 来源 | 原文/短引 | 访问日期 | 核验方式 | 主判据 | 产品后果 | 置信 |\n"
    "|---|---|---|---|---|---|---|---|---|---|\n"
)


def row(req_id, project, rubric_id, url="https://example.com/issue/1", quote="这是一条可核验的原文短引",
        date="2026-11-03", verify="GitHub API", confidence="直接", consequence="用户无法核验回答"):
    return [req_id, project, "约束描述", f"[来源]({url})", quote, date, verify, rubric_id, consequence, confidence]


BASE_ROWS = [
    row("REQ-FG-01", "FastGPT", "L1.grounding"),
    row("REQ-FG-02", "FastGPT", "L2.faithful"),
    row("REQ-FG-03", "FastGPT", "L1.must_refuse"),
    row("REQ-RF-01", "RAGFlow", "L1.pii"),
    row("REQ-RF-02", "RAGFlow", "L2.complete"),
    row("REQ-RF-03", "RAGFlow", "L2.actionable"),
    row("REQ-QA-01", "QAnything", "L1.authority"),
    row("REQ-QA-02", "QAnything", "L2.clarity"),
    row("REQ-QA-03", "QAnything", "L2.faithful"),
]

BASE_DECLARED = [["L2.compliance", "三个项目未公开讨论客服话术合规", "在 RFC 中列为待征集来源"]]


def build_doc(rows, declared=()):
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    author = "\n".join("| " + " | ".join(r) + " |" for r in declared)
    return (
        "# 需求\n\n"
        f"{CONSTRAINT_HEADING}\n\n{HEADER}{body}\n\n"
        f"{AUTHOR_HEADING}\n\n| 判据 | 理由 | 拟议处理 |\n|---|---|---|\n{author}\n"
    )


def errors_for(rows, declared=BASE_DECLARED):
    return check_requirements(build_doc(rows, declared), MINI_RUBRIC)


def has_code(errors, code):
    return any(error.startswith(code) for error in errors)


class ShippedFileTests(unittest.TestCase):
    def test_shipped_requirements_passes(self):
        rubric = yaml.safe_load(RUBRIC_PATH.read_text(encoding="utf-8"))
        text = REQ_PATH.read_text(encoding="utf-8")
        self.assertEqual(check_requirements(text, rubric), [])

    def test_shipped_has_enough_sources_and_links(self):
        text = REQ_PATH.read_text(encoding="utf-8")
        rows = section_rows(text, CONSTRAINT_HEADING, "| REQ-")
        self.assertGreaterEqual(len({r[1] for r in rows}), 3)
        self.assertGreaterEqual(len(rows), 8)
        self.assertTrue(all("https://" in r[3] for r in rows))


class CountTests(unittest.TestCase):
    def test_two_projects_rejected(self):
        errors = errors_for([r for r in BASE_ROWS if r[1] != "FastGPT"])
        self.assertTrue(has_code(errors, "C2"), errors)

    def test_too_few_constraints_rejected(self):
        errors = errors_for(BASE_ROWS[:6])
        self.assertTrue(has_code(errors, "C3"), errors)

    def test_base_fixture_passes(self):
        self.assertEqual(errors_for(BASE_ROWS), [])


class RowFieldTests(unittest.TestCase):
    def test_duplicate_id_rejected(self):
        rows = list(BASE_ROWS)
        rows[1] = list(rows[1])
        rows[1][0] = rows[0][0]
        self.assertTrue(has_code(errors_for(rows), "C4"))

    def test_bad_id_format_rejected(self):
        rows = list(BASE_ROWS)
        rows[0] = list(rows[0])
        rows[0][0] = "REQ-FASTGPT-1"
        self.assertTrue(has_code(errors_for(rows), "C4"))

    def test_missing_url_rejected(self):
        rows = list(BASE_ROWS)
        rows[0] = list(rows[0])
        rows[0][3] = "FastGPT #359"
        self.assertTrue(has_code(errors_for(rows), "C5"))

    def test_bad_access_date_rejected(self):
        rows = list(BASE_ROWS)
        rows[0] = list(rows[0])
        rows[0][5] = "2026-13-40"
        self.assertTrue(has_code(errors_for(rows), "C6"))

    def test_unknown_verify_method_rejected(self):
        rows = list(BASE_ROWS)
        rows[0] = list(rows[0])
        rows[0][6] = "道听途说"
        self.assertTrue(has_code(errors_for(rows), "C7"))

    def test_unknown_rubric_id_rejected(self):
        rows = list(BASE_ROWS)
        rows[0] = list(rows[0])
        rows[0][7] = "L9.unknown"
        self.assertTrue(has_code(errors_for(rows), "C8"))

    def test_empty_quote_rejected(self):
        rows = list(BASE_ROWS)
        rows[0] = list(rows[0])
        rows[0][4] = ""
        self.assertTrue(has_code(errors_for(rows), "C10"))

    def test_bad_confidence_rejected(self):
        rows = list(BASE_ROWS)
        rows[0] = list(rows[0])
        rows[0][9] = "猜测"
        self.assertTrue(has_code(errors_for(rows), "C11"))

    def test_empty_consequence_rejected(self):
        rows = list(BASE_ROWS)
        rows[0] = list(rows[0])
        rows[0][8] = ""
        self.assertTrue(has_code(errors_for(rows), "C12"))

    def test_wrong_column_count_rejected(self):
        rows = list(BASE_ROWS)
        rows[0] = list(rows[0])[:-1]
        self.assertTrue(has_code(errors_for(rows), "C1"))


class CoverageTests(unittest.TestCase):
    def test_uncovered_item_without_declaration_rejected(self):
        errors = errors_for(BASE_ROWS, declared=[])
        self.assertTrue(has_code(errors, "C9"), errors)

    def test_author_declaration_satisfies_coverage(self):
        self.assertEqual(errors_for(BASE_ROWS, declared=BASE_DECLARED), [])

    def test_declaration_unknown_item_rejected(self):
        errors = errors_for(BASE_ROWS, declared=[["L9.unknown", "有理由", "保留"]])
        self.assertTrue(has_code(errors, "C13"), errors)

    def test_declaration_without_reason_rejected(self):
        errors = errors_for(BASE_ROWS, declared=[["L2.compliance", "", "保留"]])
        self.assertTrue(has_code(errors, "C13"), errors)


if __name__ == "__main__":
    unittest.main()
