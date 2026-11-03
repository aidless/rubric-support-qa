#!/usr/bin/env python3
"""冻结 dev 集并生成 data/manifest.json。

冻结语义：
  - data/dev.jsonl         工作副本，可以重新生成，但重新生成必须逐字节一致。
  - data/dev.frozen.jsonl  冻结快照，与 dev.jsonl **字节相同**，之后不得再改。
  - data/manifest.json     记录每个受冻文件的 sha256、行数与冻结时间。

冻结前做内容自检（不通过则不写任何文件）：
  1. 300 条，5 个 family 各 60；
  2. id 唯一、归一化问题唯一；
  3. content_sha256 与重算一致；
  4. 每条 gold_span 必须能在其对应 doc_id 的正文里找到；
  5. stale 条必须含已过期文档与版本变更通知；overreach 条必须含权益清单；
  6. unanswerable 条必须带 L1.must_refuse。

用法：
    python3 scripts/freeze.py            # 首次冻结
    python3 scripts/freeze.py --check    # 只校验，不写文件（CI 用）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.make_dev import FAMILIES, PER_FAMILY, normalize  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def content_check(items: list[dict]) -> list[str]:
    errors: list[str] = []

    if len(items) != PER_FAMILY * len(FAMILIES):
        errors.append(f"总条数应为 {PER_FAMILY * len(FAMILIES)}，实际 {len(items)}")

    counts: dict[str, int] = {family: 0 for family in FAMILIES}
    ids: set[str] = set()
    questions: set[str] = set()

    for item in items:
        family = item.get("family")
        if family not in counts:
            errors.append(f"{item.get('id')}: 未知 family {family!r}")
            continue
        counts[family] += 1

        item_id = item.get("id", "")
        if item_id in ids:
            errors.append(f"{item_id}: id 重复")
        ids.add(item_id)

        question = normalize(item.get("question", ""))
        if question in questions:
            errors.append(f"{item_id}: 问题文本重复（归一化后）")
        questions.add(question)

        from scripts.make_dev import content_sha256  # 延迟导入，避免顶层循环依赖
        if content_sha256(item["question"], item["context"]) != item.get("content_sha256"):
            errors.append(f"{item_id}: content_sha256 不匹配")

        docs = {doc["doc_id"]: doc for doc in item.get("context", [])}
        for span in item.get("reference", {}).get("gold_spans", []):
            doc = docs.get(span.get("doc_id"))
            if doc is None:
                errors.append(f"{item_id}: gold_span 指向不存在的 doc_id {span.get('doc_id')!r}")
                continue
            if span.get("span", "") not in doc["text"]:
                errors.append(f"{item_id}: gold_span 在 {doc['doc_id']} 正文中找不到：{span.get('span')!r}")

        for doc in docs.values():
            start, end = doc.get("effective_from"), doc.get("effective_to")
            if start and end and start > end:
                errors.append(f"{item_id}: {doc['doc_id']} 生效区间倒置 {start} > {end}")

        if family == "stale":
            if not any(doc.get("effective_to") for doc in docs.values()):
                errors.append(f"{item_id}: stale 条缺少已过期文档")
            if "KB-VER-001" not in docs:
                errors.append(f"{item_id}: stale 条缺少版本变更通知")
        if family == "overreach" and "KB-AUTH-001" not in docs:
            errors.append(f"{item_id}: overreach 条缺少可承诺权益清单")
        if family == "unanswerable" and "L1.must_refuse" not in item.get("stress", []):
            errors.append(f"{item_id}: unanswerable 条未标注 L1.must_refuse")

    for family, count in counts.items():
        if count != PER_FAMILY:
            errors.append(f"{family}: 应为 {PER_FAMILY} 条，实际 {count} 条")

    return errors


def build_manifest(items: list[dict], files: dict[str, Path]) -> dict:
    entry = {}
    for rel, path in files.items():
        raw = path.read_bytes()
        entry[rel] = {
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
            "n_lines": len(read_jsonl(path)) if rel.endswith(".jsonl") else None,
        }
    families = {family: sum(1 for item in items if item["family"] == family) for family in FAMILIES}
    return {
        "schema_version": "1.0.0",
        "frozen_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {
            "name": "support-qa-zh",
            "split": "dev",
            "scenario": "中文 RAG 客服问答",
            "lang": "zh-CN",
            "n": len(items),
            "families": families,
            "construction": "synthetic_template",
        },
        "files": entry,
        "reproduce": (
            "python3 scripts/make_dev.py --seed 20261103 --out /tmp/dev.jsonl && "
            "cmp data/dev.jsonl /tmp/dev.jsonl"
        ),
        "freeze_rule": (
            "data/dev.frozen.jsonl 与 data/dev.jsonl 字节相同且冻结后不得修改；"
            "任何 rubric 改动必须在新数据集上验证，旧结论只作历史"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="冻结 dev 集并生成 manifest")
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    ap.add_argument("--force", action="store_true", help="允许覆盖已存在的冻结快照")
    args = ap.parse_args()

    dev = ROOT / "data" / "dev.jsonl"
    frozen = ROOT / "data" / "dev.frozen.jsonl"
    if not dev.exists():
        print("FAIL: data/dev.jsonl 不存在，先跑 scripts/make_dev.py", file=sys.stderr)
        return 2

    items = read_jsonl(dev)
    errors = content_check(items)
    if errors:
        print(f"FAIL: 内容自检未通过（{len(errors)} 项）", file=sys.stderr)
        for error in errors[:20]:
            print(f"  - {error}", file=sys.stderr)
        return 1

    required = {
        "data/dev.jsonl": dev,
        "rubric/rubric.v0.yaml": ROOT / "rubric" / "rubric.v0.yaml",
        "rubric/counterexamples.jsonl": ROOT / "rubric" / "counterexamples.jsonl",
        "prereg.md": ROOT / "prereg.md",
        "data/SOURCES.md": ROOT / "data" / "SOURCES.md",
    }
    missing = [rel for rel, path in required.items() if not path.exists()]
    if missing:
        print(f"FAIL: 缺少受冻文件 {missing}", file=sys.stderr)
        return 1

    if args.check:
        if not frozen.exists():
            print("FAIL: data/dev.frozen.jsonl 不存在", file=sys.stderr)
            return 1
        if frozen.read_bytes() != dev.read_bytes():
            print("FAIL: dev.frozen.jsonl 与 dev.jsonl 不一致", file=sys.stderr)
            return 1
        manifest_path = ROOT / "data" / "manifest.json"
        if not manifest_path.exists():
            print("FAIL: data/manifest.json 不存在", file=sys.stderr)
            return 1
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for rel, path in required.items():
            if manifest["files"].get(rel, {}).get("sha256") != sha256_bytes(path.read_bytes()):
                print(f"FAIL: {rel} 的 sha256 与 manifest 不符", file=sys.stderr)
                return 1
        print(f"OK: 冻结校验通过（{len(items)} 条，文件哈希一致）")
        return 0

    if frozen.exists() and not args.force and frozen.read_bytes() != dev.read_bytes():
        print("FAIL: 冻结快照已存在且与 dev.jsonl 不同；拒绝覆盖（确需重冻用 --force）",
              file=sys.stderr)
        return 1

    frozen.write_bytes(dev.read_bytes())
    files = {**required, "data/dev.frozen.jsonl": frozen}
    manifest = build_manifest(items, files)
    (ROOT / "data" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"冻结完成：{len(items)} 条，{len(files)} 个文件")
    for family, count in manifest["dataset"]["families"].items():
        print(f"  {family:12s} {count:3d}")
    for rel, info in manifest["files"].items():
        print(f"  {rel:32s} {info['sha256'][:16]}…  {info['bytes']} B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
