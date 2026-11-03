# 分歧池报告（里程碑 4）

> 结论先行：本文件交付的是 **120 条"构造池"，不是实测分歧结论**。
> 候选答案由脚本按模板构造，**不是模型输出**；`bench_verdict` / `rubric_verdict` 是按 `PLAN.md` §1.5 预注册预期填写的字段，**没有运行任何 benchmark、没有运行 rubric、没有人工标注**。
> 因此本池**不能**用来声称 rubric 正确率 ≥75%、benchmark 正确率 ≤50%、Wilson CI 不重叠或 Fleiss κ ≥0.60。

## 1. 数量与验收对照

| 项 | 目标 | 实际 | 判定 |
|---|---|---|---|
| 分歧池总条数 | ≥120 | 120 | 数量达标（构造口径） |
| D1 不可答仍作答 | ≥15 | 30 | 构造数量达标 |
| D2 字面正确但无出处 | ≥15 | 30 | 构造数量达标 |
| D3 语义等价被判错 | ≥15 | 30 | 构造数量达标 |
| D4 越权承诺 | ≥15 | 30 | 构造数量达标 |
| 人工标签 | 3 人盲标 | **0** | **未达标** |
| 真实模型输出 | 每个候选答案来自模型 | **0** | **未达标** |
| benchmark 运行 | 官方评分器 | **未运行** | **未达标** |
| rubric 运行 | rubric v1 | **未运行** | **未达标** |

**结论**：`PLAN.md` §1.8 验收表第 4 项"分歧集 ≥120 条"，本轮只能按"**构造池数量 ≥120 且四类各 ≥15**"勾选；PLAN §1.5 意义上的"分歧集"（需 benchmark 与 rubric 实际判定不一致）**尚未产生**。

## 2. 四类构造方式

| 类型 | 来源 | 候选答案怎么造 | benchmark 预期 | rubric 预期 |
|---|---|---|---|---|
| D1 不可答仍作答 | 测试集 `unanswerable` 30 条（仅范围说明） | 编造内部成本/投诉率/额度等确定结论 | `pass`（字面命中问题关键词，可能计为已作答） | `fail` / `L1.must_refuse` |
| D2 字面正确但无出处 | 测试集 `multi_hop` 前 30 条 | 核心结论正确，追加一句检索片段外的行业常识 | `pass`（关键词命中，exact-match/recall 判对） | `fail` / `L1.grounding` |
| D3 语义等价被判错 | 测试集 `multi_hop` 后 30 条 | 把规则与操作说明改成口语同义表述（含数字口语化） | `fail`（词面/单元失配） | `pass` / `L2.complete` |
| D4 越权承诺 | 测试集 `overreach` 30 条 | 流畅承诺误工费/资金占用利息/双倍定金等清单外补偿 | `pass`（语义 judge 容易放过） | `fail` / `L1.authority` |

D3 的改写只做两类操作：口语同义替换（`不支持`→`不行`、`每月`→`每个月`）、数字口语化（`7 天`→`七天`、`1–3`→`一到三`）。事实仍全部来自两份检索片段，因此 rubric 侧有 span 可依。

## 3. 记录字段

每条记录包含：

| 字段 | 含义 |
|---|---|
| `id` | `disagree-d1-001` … `disagree-d4-030` |
| `d_type` / `d_name` | D1–D4 及中文名 |
| `source_item_id` / `source_split` | 来自 `data/test.frozen.jsonl` 的具体条目 |
| `question` / `context` / `gold_spans` | 与来源条目一致，可逐条复核 |
| `candidate_answer` | **脚本构造**的候选答案（非模型输出） |
| `bench_verdict` / `bench_basis` | 预期判定与理由（**未实测**） |
| `rubric_verdict` / `rubric_basis` / `rubric_reason` | 预期判定、触发的 L1/L2 项与理由（**未实测**） |
| `evidence.rubric_gold_spans` | rubric 侧可引用的 span，已校验存在于上下文 |
| `evidence.unsourced_assertion` | 仅 D2：上下文外断言，已校验不在任何片段中 |
| `human_label` / `label_status` | 恒为 `null` / `unlabeled` |
| `verdict_status` / `measured` | 恒为 `constructed` / `false` |

## 4. 复算与校验

```bash
cd ~/rubric-support-qa

# 从冻结测试集重建分歧池（确定性）
python3 scripts/make_disagreement.py --out /tmp/pool.jsonl
cmp data/disagreement.pool.jsonl /tmp/pool.jsonl && echo "逐字节一致"

# 结构自检（数量/判定配对/证据/零人工标签）
python3 scripts/make_disagreement.py --check

# 单测
python3 -m unittest discover -s tests
```

本机实测：

```
$ python3 scripts/make_disagreement.py --check
OK: 分歧池校验通过（120 条，四类各 30 条，0 人工标签）

$ python3 -m unittest discover -s tests -p "test_disagreement.py"
Ran 11 tests in 0.073s
OK
```

文件哈希（`sha256`）：

| 文件 | 行数 | sha256 |
|---|---|---|
| `data/test.frozen.jsonl` | 800 | `8047deaa91efbf355876f025885ed47051c69367e9378585cf49ac53ebf42018` |
| `data/manifest.test.json` | — | `e49b69f140258f9535b2d068cc803bb04d3dad4ac90bddf91cbee9a8eeb67c2a` |
| `data/disagreement.pool.jsonl` | 120 | `15fc9f98d474df815f005ac034ed309fe4f2303279ca3ef14cd89c24567c58d2` |

## 5. 已知局限（必须随结论一起引用）

1. **两侧判定都是预期值**：`bench_verdict` / `rubric_verdict` 依据 `PLAN.md` §1.5 的预注册行为填写，不是任何评分器的实际输出。
2. **候选答案不是模型生成**：因此无法反映真实模型的失败分布，也无法据此估计误判率。
3. **benchmark 未指定具体实现**：PLAN 只写"RGB 官方评分器"；实际词面/召回打分器尚未接入，D3 的"词面失配"是设计假设而非测量。
4. **D2 的"正确事实"未独立核实**：三条断言是行业一般性表述，未逐条查证；它们的作用是"片段外断言"，不是"已被证实为真"。
5. **无人工标注**：`human_label` 全为 `null`，所以没有 κ、没有多数标签、没有负控制一致率。
6. **无统计结论**：没有 Wilson CI、没有正确率对比；任何"rubric 更好"的表述在本轮均不成立。
7. **池未冻结**：`disagreement.pool.jsonl` 是可重建的构造产物，标注开始后才应冻结（届时新建 `disagreement.frozen.jsonl` 与独立 manifest）。

## 6. 下一步（里程碑 4 剩余）

| 顺序 | 事项 | 依赖 | 状态 |
|---|---|---|---|
| 1 | 接入 RGB 官方评分器，对候选答案实际打分 | 数据许可、评分脚本 | 未开始 |
| 2 | 运行 rubric v1（尚未创建）得到实际判定 | RFC 意见裁决 | 未开始 |
| 3 | 只保留两侧不一致的样本，形成真实分歧池 | 1 + 2 | 未开始 |
| 4 | 3 人盲标 + 负控制 15% | 标注预算 | 未开始 |
| 5 | Wilson CI、Fleiss κ、正确率对照 | 3 + 4 | 未开始 |

在第 1–2 步完成前，本报告只能证明"构造流程可复现、四类各 30 条、证据字段自洽"，不能证明"存在有效分歧"。
