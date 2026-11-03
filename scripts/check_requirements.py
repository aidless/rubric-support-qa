#!/usr/bin/env python3
"""校验 requirements.md：来源数量、约束数量、链接、访问日期、判据映射与覆盖。

检查项（任一失败退出码 1）：
  C1  requirements.md 存在且可解析
  C2  至少 3 个不同项目
  C3  至少 8 条约束
  C4  约束 ID 唯一且形如 REQ-XX-NN
  C5  每条约束含 https 链接
  C6  每条约束有合法访问日期（YYYY-MM-DD）
  C7  核验方式在 {GitHub API, 官方文档, 二级页转引} 内
  C8  主判据 id 在 rubric 中存在
  C9  rubric 的每个 L1/L2 判据要么被覆盖，要么在"作者判断"表中声明
  C10 原文/短引非空且至少 8 个字符
  C11 置信等级在 {直接, 间接, 标题级, 转引} 内
  C12 项目、约束、产品后果三列非空
  C13 "作者判断"表必须有理由，且判据 id 在 rubric 中存在

用法：
    python3 scripts/check_requirements.py \
        --requirements requirements.md \
        --rubric rubric/rubric.v0.yaml
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

MIN_PROJECTS = 3
MIN_CONSTRAINTS = 8
VERIFY_METHODS = {"GitHub API", "官方文档", "二级页转引"}
CONFIDENCE_LEVELS = {"直接", "间接", "标题级", "转引"}
URL_RE = re.compile(r"https://[^\s)]+")
ID_RE = re.compile(r"REQ-[A-Z]{2}-\d{2}")
DATE_FMT = "%Y-%m-%d"

CONSTRAINT_HEADING = "## 约束清单"
AUTHOR_HEADING = "## 无外部来源的判据（作者判断）"
CONSTRAINT_COLUMNS = 10


def split_row(line: str) -> list[str]:
    """把 Markdown 表格行切成单元格，去掉首尾竖线。"""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def section_rows(text: str, heading: str, prefix: str) -> list[list[str]]:
    """返回指定二级标题下、以 prefix 开头的表格行。"""
    rows: list[list[str]] = []
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped == heading
            continue
        if not in_section:
            continue
        if stripped.startswith(prefix):
            rows.append(split_row(stripped))
    return rows


def rubric_item_ids(rubric: dict) -> list[str]:
    levels = rubric.get("levels") or {}
    ids: list[str] = []
    for level in ("L1", "L2"):
        for item in (levels.get(level) or {}).get("items") or []:
            if item.get("id"):
                ids.append(item["id"])
    return ids


def check_requirements(requirements_text: str, rubric: dict) -> list[str]:
    """返回错误列表；空列表 = 通过。"""
    errors: list[str] = []
    valid_ids = rubric_item_ids(rubric)
    valid_set = set(valid_ids)

    rows = section_rows(requirements_text, CONSTRAINT_HEADING, "| REQ-")
    if not rows:
        errors.append("C1: 未找到约束清单（需要 '## 约束清单' 下以 '| REQ-' 开头的表格行）")
        return errors

    projects: set[str] = set()
    seen_ids: set[str] = set()
    covered: set[str] = set()

    for row in rows:
        if len(row) != CONSTRAINT_COLUMNS:
            errors.append(f"C1: 行单元格数为 {len(row)}，应为 {CONSTRAINT_COLUMNS}：{' | '.join(row)}")
            continue
        req_id, project, constraint, source, quote, access_date, verify, rubric_id, consequence, confidence = row

        if not ID_RE.fullmatch(req_id):
            errors.append(f"C4: ID 格式不合法：{req_id}")
        if req_id in seen_ids:
            errors.append(f"C4: ID 重复：{req_id}")
        seen_ids.add(req_id)

        if not project or not constraint or not consequence:
            errors.append(f"C12: {req_id} 的项目/约束/产品后果不能为空")
        if project:
            projects.add(project)

        if not URL_RE.search(source):
            errors.append(f"C5: {req_id} 缺少 https 链接：{source}")

        if not quote or len(quote) < 8:
            errors.append(f"C10: {req_id} 原文/短引为空或过短")

        try:
            datetime.strptime(access_date, DATE_FMT)
        except ValueError:
            errors.append(f"C6: {req_id} 访问日期不合法：{access_date}")

        if verify not in VERIFY_METHODS:
            errors.append(f"C7: {req_id} 核验方式不合法：{verify}")

        if rubric_id not in valid_set:
            errors.append(f"C8: {req_id} 主判据不存在于 rubric：{rubric_id}")
        else:
            covered.add(rubric_id)

        if confidence not in CONFIDENCE_LEVELS:
            errors.append(f"C11: {req_id} 置信等级不合法：{confidence}")

    if len(projects) < MIN_PROJECTS:
        errors.append(f"C2: 项目数 {len(projects)} < {MIN_PROJECTS}：{sorted(projects)}")
    if len(rows) < MIN_CONSTRAINTS:
        errors.append(f"C3: 约束数 {len(rows)} < {MIN_CONSTRAINTS}")

    declared: set[str] = set()
    author_rows = section_rows(requirements_text, AUTHOR_HEADING, "| L")
    for row in author_rows:
        if len(row) < 2:
            errors.append(f"C13: 作者判断行列数不足：{' | '.join(row)}")
            continue
        item_id, reason = row[0], row[1]
        if item_id not in valid_set:
            errors.append(f"C13: 作者判断表判据不存在于 rubric：{item_id}")
            continue
        if not reason:
            errors.append(f"C13: {item_id} 缺少保留理由")
        declared.add(item_id)

    missing = [item for item in valid_ids if item not in covered and item not in declared]
    if missing:
        errors.append(f"C9: 以下判据既无需求覆盖，也未声明为作者判断：{missing}")

    return errors


def load_rubric(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 requirements.md")
    parser.add_argument("--requirements", default=str(ROOT / "requirements.md"))
    parser.add_argument("--rubric", default=str(ROOT / "rubric" / "rubric.v0.yaml"))
    args = parser.parse_args(argv)

    req_path = Path(args.requirements)
    if not req_path.exists():
        print(f"FAIL: 文件不存在：{req_path}", file=sys.stderr)
        return 1
    rubric_path = Path(args.rubric)
    if not rubric_path.exists():
        print(f"FAIL: rubric 不存在：{rubric_path}", file=sys.stderr)
        return 1

    text = req_path.read_text(encoding="utf-8")
    errors = check_requirements(text, load_rubric(rubric_path))
    if errors:
        print(f"FAIL: requirements 校验失败（{len(errors)} 项）", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    rows = section_rows(text, CONSTRAINT_HEADING, "| REQ-")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[1]] = counts.get(row[1], 0) + 1
    print(f"OK: 需求校验通过（{len(counts)} 个项目 / {len(rows)} 条约束）")
    for project, count in sorted(counts.items()):
        print(f"  {project:<12} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
