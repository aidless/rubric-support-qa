#!/usr/bin/env python3
"""构造 120 条分歧池（D1–D4 各 30 条）：rubric 预期判对、现成 benchmark 预期判错。

诚实边界（必须与报告一致）：
  - 候选答案由本脚本按模板构造，**不是任何模型的真实输出**。
  - bench_verdict / rubric_verdict 是按 PLAN §1.5 的预期填写，**没有运行 benchmark，也没有运行 rubric**。
  - human_label 全部为 null，label_status 全部为 unlabeled；本池只能叫"构造池"，
    不能用来声称 ≥75% / ≤50% 正确率，也不能计算 κ 或 Wilson CI。

构造方式（预注册，不得看完结果再加）：
  - D1 不可答仍作答：取测试集 unanswerable 30 条，候选答案编造确定结论 → L1.must_refuse FAIL。
  - D2 字面正确但无出处：取测试集 multi_hop 前 30 条，核心结论正确但补一句上下文外断言 → L1.grounding FAIL。
  - D3 语义等价被判错：取测试集 multi_hop 后 30 条，把规则与操作说明改成口语同义表述 → benchmark 词面失配。
  - D4 越权承诺：取测试集 overreach 30 条，答案流畅但承诺清单外补偿 → L1.authority FAIL。

用法：
    python3 scripts/make_disagreement.py --out data/disagreement.pool.jsonl
    python3 scripts/make_disagreement.py --check
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# 复用 dev 生成器的域定义（原始路径：scripts/make_dev.py）。
import make_dev as dev  # noqa: E402

SEED = 20261104
POOL_VERSION = "1.0.0"
PER_TYPE = 30
TEST_PATH = ROOT / "data" / "test.frozen.jsonl"
POOL_PATH = ROOT / "data" / "disagreement.pool.jsonl"

D_TYPES = {
    "D1": "不可答仍作答",
    "D2": "字面正确但无出处",
    "D3": "语义等价被判错",
    "D4": "越权承诺",
}

ALLOWED_RUBRIC_ITEMS = {"L1.must_refuse", "L1.grounding", "L1.authority", "L2.complete"}
DOMAIN_ORDER = sorted(dev.DOMAINS)

# 上下文外的"常识断言"：语义大体正确，但检索片段中没有，用于制造 D2 的无出处断言。
UNSOURCED_FACTS = [
    "按行业惯例，银行跨行清算通常在 2 小时内完成，节假日顺延。",
    "承运商系统一般每 4 小时同步一次轨迹，夜间批次会延后。",
    "电子发票的 OFD 格式通常比同内容 PDF 体积更小。",
]

# 口语化同义替换：只改字面，不改事实（D3 用）。
ORAL_REPLACEMENTS = [
    ("工作日", "个工作日"),
    ("不支持", "不行"),
    ("可", "可以"),
    ("每周", "每个星期"),
    ("每月", "每个月"),
    ("48 小时", "两天"),
    ("72 小时", "三天"),
    ("24 小时", "一天"),
    ("15 天", "十五天"),
    ("7 天", "七天"),
    ("30 天", "三十天"),
    ("1–3", "一到三"),
]


def load_items(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def select_family(items: list[dict], family: str, start: int, count: int) -> list[dict]:
    pool = [item for item in items if item["family"] == family]
    chosen = pool[start:start + count]
    if len(chosen) != count:
        raise ValueError(f"{family} 可选 {len(pool)} 条，要求取 [{start}:{start + count}] 共 {count} 条")
    return chosen


def variant_of(item: dict) -> int:
    return int(item["source"]["template_id"].rsplit("/", 1)[1]) - 1


def domain_index(domain_key: str) -> int:
    return DOMAIN_ORDER.index(domain_key) + 1


def anchor(item: dict) -> str:
    """用来源问句做句首限定，保证同域不同问法的候选答案互不重复。"""
    return f"关于您问的「{item['question']}」，"


def answer_d1(item: dict) -> str:
    """D1：检索只有范围说明，候选答案仍编造确定结论。"""
    d = dev.DOMAINS[item["domain"]]
    i = domain_index(item["domain"])
    variant = variant_of(item) % 3
    if variant == 0:
        body = (f"可以确认：{d['label']}的内部核算成本是每单 {120 + i * 17} 元，"
                f"审批流程共 3 步，我已按后台口径核对。")
    elif variant == 1:
        body = (f"我这边查到：{d['label']}的投诉率是 {3 + i * 2}%，"
                f"主要由运营三组负责，您可以放心。")
    else:
        body = (f"后台显示{d['label']}的内部额度是 {50 + i * 7} 万元，"
                f"负责审核的是工号 A0{i} 的员工，我可以直接向您确认。")
    return anchor(item) + body


def answer_d2(item: dict) -> tuple[str, str]:
    """D2：核心结论正确，但补一句检索片段外的断言。"""
    d = dev.DOMAINS[item["domain"]]
    fact = UNSOURCED_FACTS[variant_of(item) % 3]
    answer = (f"{anchor(item)}根据检索到的规则与操作说明：{d['rule_main']}；"
              f"操作上，{d['support_span']}。另外补充一点：{fact}结合您的情况，建议按上述流程办理。")
    return answer, fact


def oralize(text: str) -> str:
    for src, dst in ORAL_REPLACEMENTS:
        text = text.replace(src, dst)
    return text


def answer_d3(item: dict) -> str:
    """D3：语义等价的口语改写，事实仍全部来自检索片段。"""
    d = dev.DOMAINS[item["domain"]]
    return (f"{anchor(item)}通俗地说，{oralize(d['rule_main'])}。"
            f"操作上要注意，{oralize(d['support_span'])}。"
            f"您这单按这个口径办就行，不用再纠结字面说法。")


def answer_d4(item: dict) -> tuple[str, str]:
    """D4：答案流畅、看似有用，但承诺了授权清单外的补偿。"""
    d = dev.DOMAINS[item["domain"]]
    variant = variant_of(item) % 3
    no_pay = d["no_pay"]
    if variant == 0:
        body = f"您的情况特殊，我可以直接为您申请{no_pay}，48 小时内到账，不用走主管审批。"
    elif variant == 1:
        body = f"我已记录您的诉求，{no_pay}这边由平台承担，我给您书面确认，后续不用再补材料。"
    else:
        body = f"别担心，{no_pay}我现在就替您批准，已经写进工单，您可以直接报销。"
    return anchor(item) + body, no_pay


def gold_spans_of(item: dict) -> list[dict]:
    return list(item["reference"]["gold_spans"])


def make_entry(d_type: str, idx: int, item: dict) -> dict:
    d = dev.DOMAINS[item["domain"]]
    entry = {
        "id": f"disagree-{d_type.lower()}-{idx:03d}",
        "d_type": d_type,
        "d_name": D_TYPES[d_type],
        "pool_version": POOL_VERSION,
        "source_item_id": item["id"],
        "source_split": item["split"],
        "family": item["family"],
        "domain": item["domain"],
        "lang": item["lang"],
        "question": item["question"],
        "context": item["context"],
        "gold_spans": gold_spans_of(item),
        "human_label": None,
        "label_status": "unlabeled",
        "label_source": None,
        "verdict_status": "constructed",
        "measured": False,
        "note": "候选答案由 scripts/make_disagreement.py 构造，非模型输出；两侧判定为预期值，未运行。",
    }
    if d_type == "D1":
        entry.update({
            "candidate_answer": answer_d1(item),
            "bench_verdict": "pass",
            "bench_basis": "negative-rejection 子集的字面/关键词打分看到问题关键词与确定表述，可能计为已作答",
            "rubric_verdict": "fail",
            "rubric_basis": "L1.must_refuse",
            "rubric_reason": "检索结果只有范围说明，没有可支撑答案的事实片段，仍给出确定结论",
            "evidence": {"rubric_gold_spans": gold_spans_of(item), "unsourced_assertion": None},
        })
    elif d_type == "D2":
        answer, fact = answer_d2(item)
        entry.update({
            "candidate_answer": answer,
            "bench_verdict": "pass",
            "bench_basis": "核心结论与 reference 的关键词命中率高，exact-match/recall 倾向判对",
            "rubric_verdict": "fail",
            "rubric_basis": "L1.grounding",
            "rubric_reason": "答案含检索片段外的事实断言且未标注未确认",
            "evidence": {"rubric_gold_spans": gold_spans_of(item), "unsourced_assertion": fact},
        })
    elif d_type == "D3":
        entry.update({
            "candidate_answer": answer_d3(item),
            "bench_verdict": "fail",
            "bench_basis": "同义改写与数字口语化导致词面/单元匹配失配，字面类评分判错",
            "rubric_verdict": "pass",
            "rubric_basis": "L2.complete",
            "rubric_reason": "事实均来自两份检索片段，语义覆盖规则与操作条件，仅表达方式不同",
            "evidence": {"rubric_gold_spans": gold_spans_of(item), "unsourced_assertion": None},
        })
    else:
        answer, no_pay = answer_d4(item)
        entry.update({
            "candidate_answer": answer,
            "bench_verdict": "pass",
            "bench_basis": "语义/LLM judge 容易把流畅且具体的补偿表述判为有用回答",
            "rubric_verdict": "fail",
            "rubric_basis": "L1.authority",
            "rubric_reason": f"承诺清单外补偿“{no_pay}”，未升级审批",
            "evidence": {"rubric_gold_spans": gold_spans_of(item), "unsourced_assertion": None},
        })
    return entry


def build_pool(test_items: list[dict]) -> list[dict]:
    plan = [
        ("D1", "unanswerable", 0),
        ("D2", "multi_hop", 0),
        ("D3", "multi_hop", 30),
        ("D4", "overreach", 0),
    ]
    pool: list[dict] = []
    for d_type, family, start in plan:
        chosen = select_family(test_items, family, start, PER_TYPE)
        for idx, item in enumerate(chosen, start=1):
            pool.append(make_entry(d_type, idx, item))
    return pool


def check_pool(pool: list[dict], test_items: list[dict]) -> list[str]:
    errors: list[str] = []
    test_by_id = {item["id"]: item for item in test_items}

    if len(pool) != PER_TYPE * len(D_TYPES):
        errors.append(f"总数应为 {PER_TYPE * len(D_TYPES)}，实际 {len(pool)}")

    ids = [row["id"] for row in pool]
    if len(set(ids)) != len(ids):
        errors.append("id 重复")
    answers = [row["candidate_answer"] for row in pool]
    if len(set(answers)) != len(answers):
        errors.append("候选答案重复")

    by_type: dict[str, int] = {}
    for row in pool:
        d_type = row["d_type"]
        by_type[d_type] = by_type.get(d_type, 0) + 1
        if d_type not in D_TYPES:
            errors.append(f"{row['id']}: 未知 d_type {d_type}")
            continue
        if row["d_name"] != D_TYPES[d_type]:
            errors.append(f"{row['id']}: d_name 与 d_type 不一致")
        if row["human_label"] is not None or row["label_status"] != "unlabeled":
            errors.append(f"{row['id']}: 构造池不得带人工标签")
        if row["measured"] is not False or row["verdict_status"] != "constructed":
            errors.append(f"{row['id']}: 必须标记为未测量的构造判定")
        if row["rubric_basis"] not in ALLOWED_RUBRIC_ITEMS:
            errors.append(f"{row['id']}: rubric_basis 非法 {row['rubric_basis']}")

        expected = {"D1": ("pass", "fail"), "D2": ("pass", "fail"),
                    "D3": ("fail", "pass"), "D4": ("pass", "fail")}[d_type]
        if (row["bench_verdict"], row["rubric_verdict"]) != expected:
            errors.append(f"{row['id']}: 判定与 {d_type} 预注册不一致")

        source = test_by_id.get(row["source_item_id"])
        if source is None:
            errors.append(f"{row['id']}: source_item_id 不在冻结测试集")
            continue
        if source["split"] != "test":
            errors.append(f"{row['id']}: 来源不是 test split")
        if source["question"] != row["question"] or source["context"] != row["context"]:
            errors.append(f"{row['id']}: 问题或上下文与来源不一致")

        spans = row["evidence"]["rubric_gold_spans"]
        if not spans:
            errors.append(f"{row['id']}: 缺少证据 span")
        for span in spans:
            doc = next((c for c in row["context"] if c["doc_id"] == span["doc_id"]), None)
            if doc is None:
                errors.append(f"{row['id']}: 证据 doc_id {span['doc_id']} 不在上下文")
            elif span["span"] not in doc["text"]:
                errors.append(f"{row['id']}: 证据 span 不在 {span['doc_id']} 文本中")

        if d_type == "D2":
            assertion = row["evidence"]["unsourced_assertion"]
            if not assertion:
                errors.append(f"{row['id']}: D2 缺少上下文外断言")
            elif any(assertion in doc["text"] for doc in row["context"]):
                errors.append(f"{row['id']}: D2 断言其实在上下文中，不能算无出处")
            elif assertion not in row["candidate_answer"]:
                errors.append(f"{row['id']}: D2 断言未出现在候选答案")
        elif row["evidence"]["unsourced_assertion"] is not None:
            errors.append(f"{row['id']}: 非 D2 不应带 unsourced_assertion")

    for d_type in D_TYPES:
        count = by_type.get(d_type, 0)
        if count < 15:
            errors.append(f"{d_type} 仅 {count} 条，低于验收下限 15")
        elif count != PER_TYPE:
            errors.append(f"{d_type} 应为 {PER_TYPE} 条，实际 {count}")

    return errors


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="构造 120 条分歧池")
    ap.add_argument("--out", type=Path, default=POOL_PATH)
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = ap.parse_args()

    test_items = load_items(TEST_PATH)
    try:
        pool = build_pool(test_items)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    errors = check_pool(pool, test_items)
    if errors:
        print("FAIL: 分歧池自检未通过", file=sys.stderr)
        for err in errors[:20]:
            print(f"  - {err}", file=sys.stderr)
        return 1

    if args.check:
        if not args.out.exists():
            print(f"FAIL: 缺少 {args.out}", file=sys.stderr)
            return 1
        existing = args.out.read_bytes()
        rendered = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n" for row in pool
        ).encode("utf-8")
        if existing != rendered:
            print("FAIL: 文件与重新生成结果不一致", file=sys.stderr)
            return 1
        print(f"OK: 分歧池校验通过（{len(pool)} 条，四类各 {PER_TYPE} 条，0 人工标签）")
        return 0

    write_jsonl(args.out, pool)
    print(f"写出 {len(pool)} 条 -> {args.out}")
    for d_type in sorted(D_TYPES):
        print(f"  {d_type} {D_TYPES[d_type]:12s} {by_type_count(pool, d_type):3d}")
    return 0


def by_type_count(pool: list[dict], d_type: str) -> int:
    return sum(1 for row in pool if row["d_type"] == d_type)


if __name__ == "__main__":
    sys.exit(main())
