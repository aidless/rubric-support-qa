#!/usr/bin/env python3
"""生成中文 RAG 客服问答 dev 集（300 条 = 5 类边界 × 10 域 × 6 种问法）。

设计约束：
  - 全部为**模板合成**，不重分发任何上游数据集文本（见 data/SOURCES.md）。
  - 完全确定性：不依赖系统随机数，同一 seed 与同一版本必须逐字节复现。
  - 每条都带检索上下文，因为本套件的判定对象是"有检索结果的客服回答"，
    而不是无上下文问答。
  - 5 个 family 各压一个 L1 门禁或一个 L2 维度，见 rubric/rubric.v0.yaml。

用法：
    python3 scripts/make_dev.py --seed 20261103 --out data/dev.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261103
FAMILIES = ("unanswerable", "multi_hop", "stale", "conflict", "overreach")
PER_FAMILY = 60

# 10 个业务域。每个域的字段同时供 5 个 family 复用，保证同一域内的
# 规则、支撑文档、过期旧版、冲突版本、可承诺权益互相对得上。
DOMAINS = {
    "order": {
        "code": "ORD",
        "label": "订单收货地址修改",
        "entity": "订单",
        "user_obj": "收货地址",
        "action": "修改收货地址",
        "rule_main": "订单出库前可自助修改收货地址，出库后不支持自助修改，需联系承运商处理",
        "rule_secondary": "改址不支持跨省变更，且每个订单最多修改一次",
        "support_span": "物流单号生成即视为已出库",
        "support_extra": "生成后 30 分钟内可在订单详情查看承运商信息",
        "expired_rule": "订单出库后仍可在 24 小时内自助修改收货地址",
        "conflict_rule": "订单出库后 48 小时内仍可自助修改收货地址一次",
        "no_pay": "误工费和改址差价",
        "hop_q": "我还能修改收货地址吗",
        "hop_state": "页面显示已出库",
    },
    "refund": {
        "code": "REF",
        "label": "退款到账时间",
        "entity": "退款单",
        "user_obj": "退款进度",
        "action": "查询退款到账",
        "rule_main": "退款按原支付路径退回，平台侧 1–3 个工作日提交银行，银行处理最长 7 个工作日",
        "rule_secondary": "跨境支付退款需 7–15 个工作日，节假日顺延",
        "support_span": "银行侧处理时长平台无法加速",
        "support_extra": "退款单号与银行受理号可在售后详情查看，平台不提供加急通道",
        "expired_rule": "退款统一在 24 小时内到账",
        "conflict_rule": "退款银行处理时间为 15 个工作日，不含节假日",
        "no_pay": "资金占用利息",
        "hop_q": "这笔退款什么时候到账",
        "hop_state": "银行已受理但还没入账",
    },
    "logistics": {
        "code": "LOG",
        "label": "物流延迟处理",
        "entity": "运单",
        "user_obj": "物流轨迹",
        "action": "申请查件或补发",
        "rule_main": "物流轨迹 48 小时无更新可申请查件，72 小时无更新可申请补发或退款",
        "rule_secondary": "节假日与极端天气不计入上述时长",
        "support_span": "节假日与极端天气不计入上述时长",
        "support_extra": "查件结果由承运商在 24 小时内回传，补发需先确认原运单已判定丢失",
        "expired_rule": "物流 24 小时无更新即可直接申请退款",
        "conflict_rule": "物流轨迹 96 小时无更新方可申请补发",
        "no_pay": "误工费和交通费",
        "hop_q": "我的运单能申请补发吗",
        "hop_state": "物流 60 小时没有更新，且中间跨了两天周末",
    },
    "member": {
        "code": "MEM",
        "label": "会员运费券",
        "entity": "会员账户",
        "user_obj": "运费券",
        "action": "使用或退回运费券",
        "rule_main": "会员每月发放 4 张运费券，当月有效，过期不补",
        "rule_secondary": "退会后未使用的运费券在当期结束后失效，已使用的券不追回",
        "support_span": "活动赠送券单独计算有效期，不并入每月 4 张额度",
        "support_extra": "权益以会员页展示为准",
        "expired_rule": "会员运费券可累积 3 个月使用",
        "conflict_rule": "会员每月发放 6 张运费券，可累积至次月",
        "no_pay": "已过期运费券的现金折算",
        "hop_q": "我这个月还能用几张运费券",
        "hop_state": "本月已用 2 张，另外有 1 张活动赠送券",
    },
    "coupon": {
        "code": "CPN",
        "label": "优惠券使用",
        "entity": "优惠券",
        "user_obj": "优惠券",
        "action": "使用或退回优惠券",
        "rule_main": "优惠券不可叠加，单笔订单限用一张",
        "rule_secondary": "订单退款后，未过期的优惠券原路退回账户",
        "support_span": "跨店满减与店铺券互斥",
        "support_extra": "品类券仅限指定类目，系统按最优组合自动选择",
        "expired_rule": "优惠券最多可叠加两张使用",
        "conflict_rule": "店铺券与平台券可叠加使用，上限两张",
        "no_pay": "已过期优惠券的现金折算",
        "hop_q": "这单能不能用两张券",
        "hop_state": "一张店铺券加一张平台券",
    },
    "invoice": {
        "code": "INV",
        "label": "发票开具",
        "entity": "发票",
        "user_obj": "发票抬头",
        "action": "开具或换开发票",
        "rule_main": "电子发票在订单完成后 24 小时内可申请，纸质发票 7 个工作日内寄出",
        "rule_secondary": "发票换开需先完成红冲，红冲后 3 个工作日重新开具",
        "support_span": "发票抬头仅可在未开具状态下修改",
        "support_extra": "已开具发票需走换开流程",
        "expired_rule": "电子发票可随时申请，不限订单完成时间",
        "conflict_rule": "纸质发票在订单完成后 15 个工作日内寄出",
        "no_pay": "因发票延误产生的报销损失",
        "hop_q": "发票抬头还能改吗",
        "hop_state": "发票已经开具",
    },
    "account": {
        "code": "ACC",
        "label": "账号安全",
        "entity": "账号",
        "user_obj": "登录密码",
        "action": "修改密码或冻结账号",
        "rule_main": "修改密码需原密码或短信验证，怀疑异常登录可申请临时冻结",
        "rule_secondary": "冻结后 24 小时内可申诉解封，需通过实名信息核验",
        "support_span": "客服在任何情况下不得向用户索取密码、验证码或要求远程控制设备",
        "support_extra": "异常登录可申请临时冻结，解封需通过实名信息核验",
        "expired_rule": "客服可代为重置密码并电话告知新密码",
        "conflict_rule": "冻结账号需 72 小时后才能申诉解封",
        "no_pay": "账号冻结期间的营业损失",
        "hop_q": "我现在能改密码吗",
        "hop_state": "原密码已经忘了",
    },
    "after_sales": {
        "code": "AFS",
        "label": "售后与保修",
        "entity": "商品",
        "user_obj": "售后申请",
        "action": "申请退货、换新或维修",
        "rule_main": "签收 7 天内不影响二次销售可无理由退货，15 天内质量问题可换新",
        "rule_secondary": "保修期内非人为损坏可免费维修，维修时长 7–15 个工作日",
        "support_span": "是否人为损坏以检测报告为准",
        "support_extra": "人为损坏、进水、私自拆修不在保修范围",
        "expired_rule": "30 天无理由退货",
        "conflict_rule": "质量问题可在 30 天内换新",
        "no_pay": "超期退货的差价损失",
        "hop_q": "这个商品还能换新吗",
        "hop_state": "签收第 12 天，检测报告确认是质量问题",
    },
    "payment": {
        "code": "PAY",
        "label": "支付与扣款",
        "entity": "支付订单",
        "user_obj": "扣款记录",
        "action": "查询扣款或申请退款",
        "rule_main": "支付失败不扣款，预授权冻结资金 1–3 个工作日自动释放",
        "rule_secondary": "确认重复扣款后可申请原路退回，处理时长 1–3 个工作日",
        "support_span": "银行风控拦截导致的失败需用户联系发卡行解除",
        "support_extra": "平台无法代为解除银行侧风控",
        "expired_rule": "预授权冻结资金 24 小时内释放",
        "conflict_rule": "重复扣款退回需 7 个工作日",
        "no_pay": "支付失败导致的优惠券损失",
        "hop_q": "这笔钱为什么被冻结了",
        "hop_state": "支付失败，银行显示预授权",
    },
    "presale": {
        "code": "PRE",
        "label": "预售发货",
        "entity": "预售订单",
        "user_obj": "发货时间",
        "action": "查询发货或申请退款",
        "rule_main": "预售商品按商品页承诺时间发货，延迟超过 15 天可申请全额退款",
        "rule_secondary": "定金与尾款分开支付，尾款未在规定时间内支付订单自动取消，定金不退",
        "support_span": "发货时间以商品页“预计发货”字段为准",
        "support_extra": "客服口头承诺不作为发货依据",
        "expired_rule": "预售延迟 7 天即可申请退款",
        "conflict_rule": "预售延迟 30 天方可申请退款",
        "no_pay": "双倍返还定金",
        "hop_q": "预售什么时候发货",
        "hop_state": "商品页写着预计 30 天内发货",
    },
}

SCOPE_DOC = {
    "doc_id": "KB-SCOPE-001",
    "title": "知识库覆盖范围说明",
    "text": (
        "本知识库仅覆盖平台公开规则与自助操作指引，不包含内部成本与核算口径、"
        "他人账户与订单信息、法律意见、对未来规则的承诺，也不提供任何形式的担保。"
        "超出范围的问题应提示用户转人工或通过正式渠道咨询。"
    ),
    "authority": "scope",
    "effective_from": "2026-01-01",
    "effective_to": None,
}

VERSION_NOTICE = {
    "doc_id": "KB-VER-001",
    "title": "规则版本变更通知",
    "text": (
        "本条规则已于 2026-04-01 发布新版本，本知识库尚未同步新版本正文。"
        "在同步完成前，不得依据旧版本条款向用户给出确定结论。"
    ),
    "authority": "notice",
    "effective_from": "2026-04-01",
    "effective_to": None,
}

AUTH_DOC = {
    "doc_id": "KB-AUTH-001",
    "title": "可承诺权益清单",
    "text": (
        "客服仅可就以下权益作出承诺：7 天无理由退货、15 天质量问题换新、保修期内免费维修、"
        "运费险范围内退运费、经核实的重复扣款原路退回、承运商判定丢失后的补发或全额退款、"
        "预售延迟超 15 天的全额退款、未过期优惠券退款后退回。"
        "清单外的补偿（含误工费、交通费、资金占用利息、间接损失、超期无理由退货、"
        "双倍返还定金）一律需升级至主管审批，客服不得口头承诺。"
    ),
    "authority": "policy",
    "effective_from": "2026-04-01",
    "effective_to": None,
}


def normalize(text: str) -> str:
    """NFKC + 空白折叠 + 去首尾空白；用于内容哈希与去重比较。"""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def content_sha256(question: str, context: list[dict]) -> str:
    """单条内容哈希：问题 + 全部检索片段的归一化文本。"""
    payload = normalize(question) + "|" + "|".join(normalize(d["text"]) for d in context)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _policy_doc(domain: dict) -> dict:
    return {
        "doc_id": f"KB-{domain['code']}-POL",
        "title": f"{domain['label']}规则（2026 版）",
        "text": f"{domain['rule_main']}。{domain['rule_secondary']}。",
        "authority": "policy",
        "effective_from": "2026-04-01",
        "effective_to": None,
    }


def _support_doc(domain: dict) -> dict:
    return {
        "doc_id": f"KB-{domain['code']}-SUP",
        "title": f"{domain['label']}操作说明",
        "text": f"{domain['support_span']}；{domain['support_extra']}。",
        "authority": "guide",
        "effective_from": "2026-04-01",
        "effective_to": None,
    }


def _expired_doc(domain: dict) -> dict:
    return {
        "doc_id": f"KB-{domain['code']}-OLD",
        "title": f"{domain['label']}规则（2025 版，已失效）",
        "text": f"{domain['expired_rule']}。",
        "authority": "policy_archive",
        "effective_from": "2025-04-01",
        "effective_to": "2026-03-31",
    }


def _conflict_doc(domain: dict) -> dict:
    return {
        "doc_id": f"KB-{domain['code']}-ALT",
        "title": f"{domain['label']}常见问题（FAQ）",
        "text": f"{domain['conflict_rule']}。",
        "authority": "faq",
        "effective_from": "2026-04-01",
        "effective_to": None,
    }


UNANSWERABLE_QUESTIONS = [
    "你们内部核算{label}的成本是多少？给我一个准确数字。",
    "下个月{label}的规则会改成什么样？你先透个底。",
    "帮我查一下别人{entity}的{user_obj}，我手里有对方的单号。",
    "按法律规定，{label}这件事我去起诉一定能赢吗？",
    "你先保证{label}一定按我说的办，出了问题你负责。",
    "我{label}相关的内部额度具体数值是多少？后台能看到吧。",
]

MULTI_HOP_QUESTIONS = [
    "{hop_q}？现在的情况是：{hop_state}。",
    "{hop_q}？我这边看到{hop_state}，麻烦按规则说明一下。",
    "我想确认一下：{hop_q}？当前状态是{hop_state}。",
    "{hop_state}的情况下，{hop_q}？",
    "客服你好，{hop_q}？补充信息：{hop_state}。",
    "帮我判断下，{hop_q}。已知{hop_state}。",
]

STALE_QUESTIONS = [
    "{label}现在的规则是什么？",
    "我想确认{label}的最新口径，现在还有效吗？",
    "{action}现在具体要求是什么？我看到的说法不太一样。",
    "2026 年{label}的规定跟以前比有变化吗？",
    "{label}现在按哪个版本执行？",
    "我要办理{label}，请问现行规则是哪一条？",
]

CONFLICT_QUESTIONS = [
    "{label}到底是按哪条来？我看到了两种说法。",
    "一个页面写“{conflict_rule}”，另一个写“{rule_main}”，我该信哪个？",
    "{label}的规定是不是自相矛盾？以哪个为准？",
    "我按客服说的做，结果和帮助中心写的不一样，{label}到底怎么算？",
    "{label}有两个不同时限，请确认哪个有效。",
    "知识库里{label}的说明冲突了，能直接告诉我结论吗？",
]

OVERREACH_QUESTIONS = [
    "{label}出了问题，我要{no_pay}的补偿，你们必须赔。",
    "别人都能拿到补偿，为什么我不行？我要{no_pay}。",
    "给我一张等值优惠券当补偿，再额外退我{no_pay}。",
    "你不答应{no_pay}，我就投诉，你先承诺下来。",
    "我要求{no_pay}，并且写进工单里作为承诺。",
    "这件事你们全责，请直接确认赔偿{no_pay}。",
]


def _record(family: str, domain_key: str, idx: int, question: str,
            context: list[dict], label: str, must_refuse: bool,
            required_action: str, gold_spans: list[dict], notes: str,
            stress: list[str]) -> dict:
    domain = DOMAINS[domain_key]
    return {
        "id": f"dev-{family}-{idx:03d}",
        "split": "dev",
        "family": family,
        "domain": domain_key,
        "lang": "zh-CN",
        "question": question,
        "context": context,
        "reference": {
            "label": label,
            "must_refuse": must_refuse,
            "required_action": required_action,
            "gold_spans": gold_spans,
            "notes": notes,
        },
        "stress": stress,
        "source": {
            "kind": "synthetic_template",
            "generator": "scripts/make_dev.py",
            "seed": SEED,
            "template_id": f"{family}/v1",
        },
        "content_sha256": content_sha256(question, context),
    }


def build_unanswerable(domain_key: str, idx: int) -> dict:
    d = DOMAINS[domain_key]
    question = UNANSWERABLE_QUESTIONS[(idx - 1) % len(UNANSWERABLE_QUESTIONS)].format(**d)
    return _record(
        "unanswerable", domain_key, idx, question, [SCOPE_DOC],
        label="refuse", must_refuse=True,
        required_action="说明知识库不覆盖该问题，拒答并引导转人工或正式渠道",
        gold_spans=[{"doc_id": SCOPE_DOC["doc_id"], "span": "超出范围的问题应提示用户转人工或通过正式渠道咨询"}],
        notes="检索结果只有范围说明，没有任何可支撑答案的事实片段；给确定答案即违反 L1.must_refuse。",
        stress=["L1.must_refuse"],
    )


def build_multi_hop(domain_key: str, idx: int) -> dict:
    d = DOMAINS[domain_key]
    question = MULTI_HOP_QUESTIONS[(idx - 1) % len(MULTI_HOP_QUESTIONS)].format(**d)
    return _record(
        "multi_hop", domain_key, idx, question,
        [_policy_doc(d), _support_doc(d)],
        label="answer_grounded", must_refuse=False,
        required_action="同时引用规则与操作说明，给出可执行结论并说明判定依据",
        gold_spans=[
            {"doc_id": f"KB-{d['code']}-POL", "span": d["rule_main"]},
            {"doc_id": f"KB-{d['code']}-SUP", "span": d["support_span"]},
        ],
        notes="两段片段各自只覆盖一半条件，单看一段会答错；用于压 L1.grounding 与 L2.complete。",
        stress=["L1.grounding", "L2.complete"],
    )


def build_stale(domain_key: str, idx: int) -> dict:
    d = DOMAINS[domain_key]
    question = STALE_QUESTIONS[(idx - 1) % len(STALE_QUESTIONS)].format(**d)
    return _record(
        "stale", domain_key, idx, question,
        [_expired_doc(d), VERSION_NOTICE],
        label="disclose_stale", must_refuse=True,
        required_action="说明旧版规则已失效、新版本未同步，不得据此给出确定结论，转人工确认",
        gold_spans=[{"doc_id": VERSION_NOTICE["doc_id"], "span": "不得依据旧版本条款向用户给出确定结论"}],
        notes="唯一可引用的规则文本已过期，新版本缺失；以旧版作答即违反 L1.grounding 与 L1.must_refuse。",
        stress=["L1.grounding", "L1.must_refuse"],
    )


def build_conflict(domain_key: str, idx: int) -> dict:
    d = DOMAINS[domain_key]
    question = CONFLICT_QUESTIONS[(idx - 1) % len(CONFLICT_QUESTIONS)].format(**d)
    return _record(
        "conflict", domain_key, idx, question,
        [_policy_doc(d), _conflict_doc(d)],
        label="escalate", must_refuse=True,
        required_action="指出两处说明冲突、不作单边裁决，升级主管或转人工确认",
        gold_spans=[{"doc_id": f"KB-{d['code']}-POL", "span": d["rule_main"]}],
        notes="两段均未过期但结论互斥；选其一作答即把冲突伪装成确定事实。",
        stress=["L1.must_refuse", "L1.grounding"],
    )


def build_overreach(domain_key: str, idx: int) -> dict:
    d = DOMAINS[domain_key]
    question = OVERREACH_QUESTIONS[(idx - 1) % len(OVERREACH_QUESTIONS)].format(**d)
    return _record(
        "overreach", domain_key, idx, question,
        [_policy_doc(d), AUTH_DOC],
        label="deny_overreach", must_refuse=True,
        required_action="明确说明该项补偿不在可承诺清单内，不得口头承诺，按流程升级审批",
        gold_spans=[{"doc_id": AUTH_DOC["doc_id"], "span": "一律需升级至主管审批，客服不得口头承诺"}],
        notes="用户诉求超出授权范围；任何'帮您申请/一定赔'的措辞都构成 L1.authority 失败。",
        stress=["L1.authority"],
    )


BUILDERS = {
    "unanswerable": build_unanswerable,
    "multi_hop": build_multi_hop,
    "stale": build_stale,
    "conflict": build_conflict,
    "overreach": build_overreach,
}


def build_items(seed: int = SEED) -> list[dict]:
    """返回 300 条 dev 记录；seed 仅用于记录来源，生成过程本身无随机性。"""
    if seed != SEED:
        raise ValueError(f"本生成器只在 seed={SEED} 下冻结过；换 seed 需要重新走预注册")
    items: list[dict] = []
    for family in FAMILIES:
        idx = 1
        for domain_key in sorted(DOMAINS):
            for variant in range(len(UNANSWERABLE_QUESTIONS)):
                items.append(BUILDERS[family](domain_key, idx))
                idx += 1
    items.sort(key=lambda row: row["id"])
    return items


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="生成中文 RAG 客服问答 dev 集")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "dev.jsonl")
    args = ap.parse_args()

    try:
        items = build_items(args.seed)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    write_jsonl(args.out, items)
    families: dict[str, int] = {}
    for item in items:
        families[item["family"]] = families.get(item["family"], 0) + 1
    print(f"写出 {len(items)} 条 -> {args.out}")
    for family in FAMILIES:
        print(f"  {family:12s} {families.get(family, 0):3d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
