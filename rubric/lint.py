#!/usr/bin/env python3
"""rubric 一致性检查（lint）。

检查项（任一失败即退出码 1，CI 红）：
  R1  schema_version / rubric_id / version 齐备，且 schema_version == 1
  R2  L2 权重和为 1（误差 <= 1e-9），每个权重在 (0, 1]
  R3  pass_threshold 可达：0 < threshold <= 满分（Σ weight × max_scale）
  R4  每个 L1 项至少 1 条反例，且反例 id 在 counterexamples.jsonl 中存在
  R5  反例必须有 answer / why_fail，且其 l1_id 指向真实 L1 项；反例 id 唯一
  R6  L2 维度互斥：每个维度必须用 distinguishes_from 显式声明与其余维度的边界
  R7  L1 项 evidence_required 必须为 true（证据不足不能默认通过）
  R8  L3.evidence_gap_verdict 必须是 REVIEW（fail-closed）
  R9  conflict_policy.precedence 覆盖所有 priority 取值；tie_break 为 fail_closed
  R10 conflict_policy.l1_priority_map 的键集合必须与 L1 项集合完全一致
  R11 authority_whitelist 非空、id 唯一、每项有 item 与 scope
  R12 cross_version_compare 必须为 false（禁止跨版本比分数）

用法：
    python3 rubric/lint.py --rubric rubric/rubric.v0.yaml \
                           --counterexamples rubric/counterexamples.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FATAL = "FAIL"
REVIEW_VERDICT = "REVIEW"


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} JSON 解析失败：{exc}") from exc
    return rows


def lint_rubric(rubric: dict, counterexamples: list[dict]) -> list[str]:
    """返回错误列表；空列表 = 通过。"""
    errors: list[str] = []

    # R1
    if rubric.get("schema_version") != 1:
        errors.append("R1: schema_version 必须为 1")
    for key in ("rubric_id", "version", "scenario"):
        if not rubric.get(key):
            errors.append(f"R1: 缺少字段 {key}")

    levels = rubric.get("levels") or {}
    l1_items = ((levels.get("L1") or {}).get("items")) or []
    l2 = levels.get("L2") or {}
    l2_items = l2.get("items") or []
    l3 = levels.get("L3") or {}

    # R7
    if not l1_items:
        errors.append("R7: L1 项为空")
    l1_ids: list[str] = []
    for item in l1_items:
        item_id = item.get("id", "")
        l1_ids.append(item_id)
        if item.get("evidence_required") is not True:
            errors.append(f"R7: {item_id} 必须声明 evidence_required: true")
        if not item.get("fail_if"):
            errors.append(f"R7: {item_id} 缺少 fail_if")
        if item.get("priority") not in (rubric.get("conflict_policy") or {}).get("precedence", []):
            errors.append(f"R9: {item_id} 的 priority {item.get('priority')!r} 不在 precedence 中")

    if len(set(l1_ids)) != len(l1_ids):
        errors.append("R7: L1 项 id 重复")

    # R2 / R3
    weights = []
    max_scale = 0
    scale = l2.get("scale") or [0, 1, 2]
    if isinstance(scale, list) and scale:
        max_scale = max(scale)
    for item in l2_items:
        weight = item.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool):
            errors.append(f"R2: {item.get('id')} 的 weight 不是数字")
            continue
        if not (0 < weight <= 1):
            errors.append(f"R2: {item.get('id')} 的 weight {weight} 不在 (0, 1]")
        weights.append(float(weight))
    if l2_items and abs(sum(weights) - 1.0) > 1e-9:
        errors.append(f"R2: L2 权重和为 {sum(weights):.6f}，应为 1.0")

    threshold = l2.get("pass_threshold")
    max_score = sum(weights) * max_scale if weights else 0.0
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        errors.append("R3: 缺少 pass_threshold")
    elif not (0 < threshold <= max_score):
        errors.append(f"R3: pass_threshold {threshold} 不可达（满分 {max_score}）")

    l2_ids = [item.get("id", "") for item in l2_items]
    if len(set(l2_ids)) != len(l2_ids):
        errors.append("R6: L2 维度 id 重复")
    # R6
    for item in l2_items:
        others = {other for other in l2_ids if other != item.get("id")}
        declared = set(item.get("distinguishes_from") or [])
        if others - declared:
            missing = sorted(others - declared)
            errors.append(f"R6: {item.get('id')} 未声明与 {missing} 的边界")
        if not item.get("definition"):
            errors.append(f"R6: {item.get('id')} 缺少 definition")

    # R8
    if l3.get("evidence_gap_verdict") != REVIEW_VERDICT:
        errors.append(f"R8: L3.evidence_gap_verdict 必须为 {REVIEW_VERDICT}")

    # R9 / R10
    policy = rubric.get("conflict_policy") or {}
    precedence = policy.get("precedence") or []
    if policy.get("tie_break") != "fail_closed":
        errors.append("R9: tie_break 必须为 fail_closed")
    if policy.get("cross_version_compare") is not False:  # R12
        errors.append("R12: cross_version_compare 必须为 false")
    priority_map = policy.get("l1_priority_map") or {}
    if set(priority_map) != set(l1_ids):
        errors.append(f"R10: l1_priority_map 键集合与 L1 项不一致（map={sorted(priority_map)}, l1={sorted(l1_ids)}）")
    for key, value in priority_map.items():
        if value not in precedence:
            errors.append(f"R10: {key} 映射到未知优先级 {value!r}")

    # R4 / R5
    ce_by_id: dict[str, dict] = {}
    for ce in counterexamples:
        ce_id = ce.get("ce_id", "")
        if ce_id in ce_by_id:
            errors.append(f"R5: 反例 id 重复 {ce_id}")
        ce_by_id[ce_id] = ce
        if not ce.get("answer") or not ce.get("why_fail"):
            errors.append(f"R5: {ce_id} 缺少 answer 或 why_fail")
        if ce.get("l1_id") not in l1_ids:
            errors.append(f"R5: {ce_id} 的 l1_id {ce.get('l1_id')!r} 不存在")

    covered: dict[str, int] = {item_id: 0 for item_id in l1_ids}
    for item in l1_items:
        for ce_id in item.get("counterexamples") or []:
            if ce_id not in ce_by_id:
                errors.append(f"R4: {item.get('id')} 引用的反例 {ce_id} 不存在")
                continue
            if ce_by_id[ce_id].get("l1_id") != item.get("id"):
                errors.append(f"R4: {ce_id} 的 l1_id 与引用它的 {item.get('id')} 不符")
            covered[item.get("id")] = covered.get(item.get("id"), 0) + 1
    for item_id, count in covered.items():
        if count < 1:
            errors.append(f"R4: {item_id} 没有反例")

    # R11
    whitelist = rubric.get("authority_whitelist") or []
    if not whitelist:
        errors.append("R11: authority_whitelist 为空")
    seen_aw = set()
    for entry in whitelist:
        aw_id = entry.get("id", "")
        if aw_id in seen_aw:
            errors.append(f"R11: 白名单 id 重复 {aw_id}")
        seen_aw.add(aw_id)
        if not entry.get("item") or not entry.get("scope"):
            errors.append(f"R11: 白名单项 {aw_id} 缺少 item 或 scope")

    return errors


def lint_files(rubric_path: Path, ce_path: Path) -> list[str]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return ["缺少 PyYAML：python3 -m pip install PyYAML"]

    rubric = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
    if not isinstance(rubric, dict):
        return [f"rubric 顶层不是映射：{rubric_path}"]
    counterexamples = read_jsonl(ce_path)
    return lint_rubric(rubric, counterexamples)


def main() -> int:
    ap = argparse.ArgumentParser(description="rubric lint")
    ap.add_argument("--rubric", type=Path, default=ROOT / "rubric" / "rubric.v0.yaml")
    ap.add_argument("--counterexamples", type=Path,
                    default=ROOT / "rubric" / "counterexamples.jsonl")
    args = ap.parse_args()

    try:
        errors = lint_files(args.rubric, args.counterexamples)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    if errors:
        print(f"{FATAL}: rubric lint 未通过（{len(errors)} 项）", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"OK: rubric lint 通过（{args.rubric}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
