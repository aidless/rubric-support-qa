# rubric-support-qa（P1）

> 结论先行：**本轮（P1 里程碑 3）交付的是"13 条真实需求来源 + RFC-001 草案 + 需求机器校验"**，叠加此前的 300 条 dev 集、预注册冻结、rubric lint 与校准库。
> 没有跑过任何模型或裁判，因此**没有任何准确率 / κ / 对照结论**；H1–H4 全部未检验。
> RFC **未公示、0 条外部意见、0 名非作者签字**；S3/S4/S5 均未开始。

## 状态

| 项 | 状态 | 证据 |
|---|---|---|
| 真实需求来源（3 项目 / 13 条带链接约束） | 完成 | `requirements.md` |
| RFC-001（需求→判据→失败后果 + 8 项拟议 diff） | **草案，未公示** | `RFC-001-rubric.md` |
| 外部意见裁决 | **0 条意见 / 0 条改变判定** | `decisions.md` |
| 独立签字 | **0 名非作者** | `SIGNOFF.md` |
| 需求机器校验（来源数/链接/日期/映射/覆盖） | 完成，当前通过 | `python3 scripts/check_requirements.py` |
| 里程碑 3 偏差记录 | 完成 | `deviations.md` |
| dev 集 300 条（5 类边界 × 60） | 完成 | `data/dev.jsonl`、`data/dev.frozen.jsonl` |
| 预注册冻结 | 完成 | `prereg.md` + `data/manifest.json`（sha256 固定） |
| rubric v0（L1/L2/L3 + 冲突优先级 + 授权清单） | 完成 | `rubric/rubric.v0.yaml` |
| rubric lint（12 组规则） | 完成，当前通过 | `python3 rubric/lint.py` |
| 反例库（每个 L1 项 2 条） | 完成，8 条 | `rubric/counterexamples.jsonl` |
| 校准库（κ / Pearson / Spearman / Fleiss / 漂移 / Wilson） | 完成，纯函数 | `calibration/` |
| 单测 | 92 个，全通过 | `python3 -m unittest discover -s tests` |
| rubric v1（经意见裁决后） | **未开始** | — |
| 冻结测试集 800 条 | **未开始** | — |
| rubric vs benchmark 分歧结论 | **未开始** | — |
| 人工标注 / κ 实测 | **未开始** | — |

## 命令

```bash
cd ~/rubric-support-qa

# 1) 重新生成 dev 集（确定性，必须与已冻结文件逐字节一致）
python3 scripts/make_dev.py --seed 20261103 --out data/dev.jsonl
cmp data/dev.jsonl data/dev.frozen.jsonl && echo "字节一致"

# 2) 冻结 / 校验冻结
python3 scripts/freeze.py            # 首次或 --force 时写冻结快照与 manifest
python3 scripts/freeze.py --check    # CI：只校验哈希，不写文件

# 3) 需求文档校验（来源数、链接、访问日期、判据映射与覆盖）
python3 scripts/check_requirements.py \
  --requirements requirements.md \
  --rubric rubric/rubric.v0.yaml

# 4) rubric lint
python3 rubric/lint.py \
  --rubric rubric/rubric.v0.yaml \
  --counterexamples rubric/counterexamples.jsonl

# 5) 单测
python3 -m unittest discover -s tests -v

# 或者一条命令
make check
```

实测输出（本机，Python 3.12）：

```
$ python3 scripts/make_dev.py --seed 20261103 --out data/dev.jsonl
写出 300 条 -> data/dev.jsonl
  unanswerable  60
  multi_hop     60
  stale         60
  conflict      60
  overreach     60

$ python3 scripts/check_requirements.py
OK: 需求校验通过（3 个项目 / 13 条约束）
  FastGPT      5
  QAnything    3
  RAGFlow      5

$ python3 rubric/lint.py
OK: rubric lint 通过（rubric/rubric.v0.yaml）

$ python3 scripts/freeze.py --check
OK: 冻结校验通过（300 条，文件哈希一致）

$ python3 -m unittest discover -s tests
Ran 92 tests in 0.415s
OK
```

## 目录

```
rubric-support-qa/
  README.md
  requirements.md                # 3 个项目 / 13 条带链接约束
  RFC-001-rubric.md              # RFC 草案（未公示）
  decisions.md                   # 外部意见裁决（0 条）
  SIGNOFF.md                     # 非作者签字（0 人）
  deviations.md                  # 里程碑偏差日志
  prereg.md                      # 预注册：H1–H4、样本、分析计划、停止规则
  data/
    dev.jsonl                    # 300 条工作副本
    dev.frozen.jsonl             # 冻结快照（与 dev.jsonl 字节相同）
    manifest.json                # 各文件 sha256 / 行数 / 冻结时间
    SOURCES.md                   # 如实声明：100% 模板合成
  rubric/
    rubric.v0.yaml               # L1 门禁 / L2 加权 / L3 证据 + 冲突优先级 + 授权清单
    counterexamples.jsonl        # 每个 L1 项 2 条反例
    lint.py                      # 12 组一致性检查
  scripts/
    make_dev.py                  # 确定性生成器（seed=20261103）
    freeze.py                    # 冻结 + 内容自检 + manifest
    check_requirements.py        # 需求文档结构与映射校验
  calibration/
    agreement.py                 # κ / Pearson / Spearman / Fleiss
    drift.py                     # FNR-FPR 漂移
    intervals.py                 # Wilson 95% CI
  tests/                         # 92 个单测
```

## dev 集构成

| family | 条数 | 检索形态 | 期望标签 | 主要压 |
|---|---|---|---|---|
| `unanswerable` | 60 | 只有知识库范围说明 | `refuse` | `L1.must_refuse` |
| `multi_hop` | 60 | 规则 + 操作说明，各自只覆盖一半条件 | `answer_grounded` | `L1.grounding`、`L2.complete` |
| `stale` | 60 | 已失效旧版 + 版本变更通知 | `disclose_stale` | `L1.grounding`、`L1.must_refuse` |
| `conflict` | 60 | 政策与 FAQ 互斥且均未过期 | `escalate` | `L1.must_refuse` |
| `overreach` | 60 | 政策 + 可承诺权益清单 | `deny_overreach` | `L1.authority` |

每条记录含 `id / family / domain / question / context / reference / stress / source / content_sha256`，字段说明见 [data/SOURCES.md](data/SOURCES.md)。

## rubric 三级

| 层级 | 作用 | 失败后果 |
|---|---|---|
| L1 门禁 | PII、可溯源、授权承诺、必须拒答 | 任一 fail → 整体 FAIL，L2 不计分 |
| L2 加权 | complete .30 / faithful .25 / compliance .20 / actionable .15 / clarity .10 | 加权 < 1.60 → FAIL |
| L3 证据 | 每个判定需 span / 反例 | 证据缺失 → REVIEW（fail-closed），不得 PASS |

冲突优先级：`safety_legal > grounding > refusal > task_completion > style`；同层取更严格，禁止"平均一下"；禁止跨版本比分数。

## 需求来源（里程碑 3）

`requirements.md` 记录 3 个真实项目、13 条带链接约束；每条含原文短引、访问日期（2026-11-03）、核验方式、主判据与产品后果。

| 项目 | 条数 | 来源 | 主要映射 |
|---|---|---|---|
| FastGPT | 5 | issue #359 / #587 / #1406 / #1446 / #4094 | `L1.grounding`、`L1.must_refuse`、`L2.faithful`、`L2.actionable` |
| RAGFlow | 5 | issue #12532 / #7232 / #6261 + 官方 FAQ | `L1.grounding`、`L1.must_refuse`、`L1.pii`、`L2.faithful`、`L2.actionable` |
| QAnything | 3 | issue #463 + 官方知识库 API 文档 | `L1.authority`、`L2.complete`、`L2.clarity` |

证据强度：直接 10 条、间接 2 条、标题级 1 条；`L2.compliance` 无外部来源，已声明为"作者判断"。RFC 的 8 项拟议 diff 见 `RFC-001-rubric.md`，**未公示、未签字、未实测**。

## 复用映射（代码内已标注原始路径）

| 复用内容 | 来源 | 落点 |
|---|---|---|
| `kappa` / `pearson` / `spearman` 与门禁阈值 | `/home/liuzewen/gh-publication-audit-20261029/judge-calibration-api/human_gold_consistency.py` | `calibration/agreement.py` |
| `compute_fnr_fpr` / `load_baseline` / `check_drift` 与 0.05 阈值 | `/home/liuzewen/gh-publication-audit-20261029/judge-calibration-api/calibration_monitor.py` | `calibration/drift.py` |
| Wilson 95% CI | `/home/liuzewen/eval-gate/eval_gate/stats.py`（P2 产物） | `calibration/intervals.py` |

改造（而非照搬）：
- 原两个脚本都是"CLI + 硬编码路径 + 绑定 `judge_run`"；这里全部抽成纯函数，不读 `F:\...`，不调模型。
- `fleiss_kappa` 为新增（原仓没有），用于预注册 H3 的三家裁判一致性。
- 原文的"连续两次漂移 → UNCALIBRATED"改成 `consecutive_drift_state(history)`，把状态交给调用方。

## 边界与未做

- **不 push、不建远端、不发布、不发 outreach**；本仓仅本地 `git init` + commit。
- 不重分发 RGB / CRUD-RAG 等上游原文；本 dev 集为模板合成。
- dev 集**不能**用来声称覆盖真实用户问句分布。
- 未跑任何裁判，故 README 与 prereg 均不给出任何效果数字。
- rubric v0 仅通过机器 lint，**未经过外部评审、未签字**。
- RFC-001 **未公示**：0 天公示、0 条外部意见、0 名非作者签字；S3/S4/S5 未完成。
- 需求来源中 2 条为间接证据、1 条为标题级证据；`L2.compliance` 无外部来源，已在 `requirements.md` 标为"作者判断"。
- `rubric.v1.yaml` **未创建**；RFC 中的 8 项 diff 仅为提案，未冻结、未实测。
