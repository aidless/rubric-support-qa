#!/usr/bin/env python3
"""冻结 800 条测试集：内容自检 + 与 dev 零重叠 + 生成 data/manifest.test.json。

用法：
    python3 scripts/freeze_test.py            # 冻结（写 test.frozen.jsonl + manifest.test.json）
    python3 scripts/freeze_test.py --check    # 只校验，不写文件
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import make_dev as dev  # noqa: E402
import make_test as testgen  # noqa: E402

N_TOTAL = 800
KIND_COUNTS = {
    "synthetic_boundary": 600,
    "real_derived_paraphrase": 100,
    "adversarial_injection": 100,
}
ALLOWED_LABELS = {
    "refuse", "answer_grounded", "disclose_stale", "escalate",
    "deny_overreach", "refuse_injection", "ignore_injection",
}
TEST_PATH = ROOT / "data" / "test.jsonl"
FROZEN_PATH = ROOT / "data" / "test.frozen.jsonl"
MANIFEST_PATH = ROOT / "data" / "manifest.test.json"
DEV_PATH = ROOT / "data" / "dev.frozen.jsonl"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def content_check(items: list[dict], dev_items: list[dict]) -> list[str]:
    errors: list[str] = []
    if len(items) != N_TOTAL:
        errors.append(f"总数 {len(items)} != {N_TOTAL}")
    if len({item["id"] for item in items}) != len(items):
        errors.append("id 不唯一")
    if len({item["question"] for item in items}) != len(items):
        errors.append("问题不唯一")
    if len({item["content_sha256"] for item in items}) != len(items):
        errors.append("content_sha256 不唯一")

    kinds: dict[str, int] = {}
    families: dict[str, int] = {}
    for item in items:
        if item.get("split") != "test":
            errors.append(f"{item['id']} split != test")
        kind = item.get("source", {}).get("kind", "")
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == "synthetic_boundary":
            families[item["family"]] = families.get(item["family"], 0) + 1
        if item["reference"]["label"] not in ALLOWED_LABELS:
            errors.append(f"{item['id']} 未知 label：{item['reference']['label']}")
        expected = dev.content_sha256(item["question"], item["context"])
        if expected != item["content_sha256"]:
            errors.append(f"{item['id']} content_sha256 不匹配")

        doc_texts = {doc["doc_id"]: doc["text"] for doc in item["context"]}
        for span in item["reference"]["gold_spans"]:
            doc_id = span["doc_id"]
            if doc_id not in doc_texts:
                errors.append(f"{item['id']} gold span 引用不存在的文档：{doc_id}")
            elif span["span"] not in doc_texts[doc_id]:
                errors.append(f"{item['id']} gold span 不在 {doc_id}：{span['span']}")

    for kind, expected in KIND_COUNTS.items():
        if kinds.get(kind, 0) != expected:
            errors.append(f"{kind} 数量 {kinds.get(kind, 0)} != {expected}")

    boundary_families = {
        family: count for family, count in families.items()
        if family in dev.FAMILIES
    }
    for family in dev.FAMILIES:
        if boundary_families.get(family, 0) != 120:
            errors.append(f"边界集 {family} 数量 {boundary_families.get(family, 0)} != 120")

    dev_hashes = {item["content_sha256"] for item in dev_items}
    overlap = dev_hashes & {item["content_sha256"] for item in items}
    if overlap:
        errors.append(f"与 dev 集内容重叠 {len(overlap)} 条")
    return errors


def build_manifest(items: list[dict]) -> dict:
    kinds: dict[str, int] = {}
    families: dict[str, int] = {}
    for item in items:
        kind = item["source"]["kind"]
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == "synthetic_boundary":
            families[item["family"]] = families.get(item["family"], 0) + 1
    files = {}
    for rel in ("data/test.jsonl", "data/test.frozen.jsonl", "data/dev.frozen.jsonl"):
        path = ROOT / rel
        payload = path.read_bytes()
        files[rel] = {
            "bytes": len(payload),
            "n_lines": sum(1 for line in payload.decode("utf-8").splitlines() if line.strip()),
            "sha256": sha256_file(path),
        }
    return {
        "schema_version": "1.0.0",
        "dataset": {
            "name": "support-qa-zh", "lang": "zh-CN", "split": "test", "n": len(items),
            "scenario": "中文 RAG 客服问答",
            "kinds": kinds,
            "families": families,
            "construction": "600 模板边界 + 100 真实需求改写 + 100 对抗注入",
            "dev_overlap": 0,
        },
        "files": files,
        "frozen_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reproduce": "python3 scripts/make_test.py --seed 20261104 --out /tmp/test.jsonl && cmp data/test.jsonl /tmp/test.jsonl",
        "freeze_rule": "data/test.frozen.jsonl 与 data/test.jsonl 字节相同且冻结后不得修改；冻结必须先于任何 rubric v1 运行；任何 rubric 改动必须在新测试集上验证，旧结论只作历史",
    }


def check_manifest(items: list[dict]) -> list[str]:
    errors: list[str] = []
    if not MANIFEST_PATH.exists():
        return [f"manifest 不存在：{MANIFEST_PATH}"]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for rel, meta in manifest.get("files", {}).items():
        path = ROOT / rel
        if not path.exists():
            errors.append(f"manifest 文件不存在：{rel}")
            continue
        if sha256_file(path) != meta["sha256"]:
            errors.append(f"sha256 不一致：{rel}")
        if path.stat().st_size != meta["bytes"]:
            errors.append(f"bytes 不一致：{rel}")
    if TEST_PATH.read_bytes() != FROZEN_PATH.read_bytes():
        errors.append("test.jsonl 与 test.frozen.jsonl 字节不同")
    errors.extend(content_check(items, load_jsonl(DEV_PATH)))
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="冻结 800 条测试集")
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = ap.parse_args(argv)

    for path in (TEST_PATH, DEV_PATH):
        if not path.exists():
            print(f"FAIL: 缺少文件 {path}", file=sys.stderr)
            return 1
    items = load_jsonl(TEST_PATH)
    dev_items = load_jsonl(DEV_PATH)

    if args.check:
        errors = check_manifest(items)
        if errors:
            print(f"FAIL: 测试集冻结校验失败（{len(errors)} 项）", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        print(f"OK: 测试集冻结校验通过（{len(items)} 条，文件哈希一致，与 dev 零重叠）")
        return 0

    errors = content_check(items, dev_items)
    if errors:
        print(f"FAIL: 测试集内容自检失败（{len(errors)} 项）", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    shutil.copyfile(TEST_PATH, FROZEN_PATH)
    MANIFEST_PATH.write_text(
        json.dumps(build_manifest(items), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OK: 已冻结 {len(items)} 条 -> {FROZEN_PATH}")
    print(f"OK: manifest -> {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
