# dev 集来源说明（SOURCES）

> 结论先行：**本 dev 集 100% 为模板合成，未包含、未重分发任何上游数据集的原文。**

## 1. 构成

| 项 | 值 |
|---|---|
| 文件 | `data/dev.jsonl`（工作副本）、`data/dev.frozen.jsonl`（冻结快照，字节相同） |
| 条数 | 300 |
| 构造脚本 | `scripts/make_dev.py` |
| 随机种子 | `20261103`（脚本本身无随机分支，seed 仅作版本标记） |
| 构造方式 | 10 个业务域 × 6 种问法 × 5 个边界族 = 300 |
| 语言 | zh-CN |
| 许可 | 本仓原创，随本仓 LICENSE 发布 |

## 2. 每条记录的字段

| 字段 | 含义 |
|---|---|
| `id` | `dev-<family>-<NNN>`，唯一 |
| `split` | 固定 `dev` |
| `family` | `unanswerable` / `multi_hop` / `stale` / `conflict` / `overreach` |
| `domain` | 10 个业务域之一（order/refund/logistics/member/coupon/invoice/account/after_sales/payment/presale） |
| `question` | 用户问句（模板生成） |
| `context` | 检索片段列表：`doc_id / title / text / authority / effective_from / effective_to` |
| `reference` | 期望行为：`label`、`must_refuse`、`required_action`、`gold_spans`、`notes` |
| `stress` | 本条主要压的判据 id（对应 `rubric.v0.yaml`） |
| `source` | `kind=synthetic_template`、生成器路径、seed、模板 id |
| `content_sha256` | `sha256(normalize(question) + "\|" + normalize(每个 context.text))` |

`normalize` 定义：NFKC 归一化 → 空白折叠为单个空格 → 去首尾空白（见 `scripts/make_dev.py`）。

## 3. 刻意不做的三件事

1. **不重分发 RGB / CRUD-RAG / 其它公开数据集的原文**。本集与它们无关；未来若引入，只发布 `id + 我们的标签 + 复算脚本`，原文是否重分发按上游许可单独决定。
2. **不冒充真实用户问句**。所有问句都来自模板；`reference` 里的"期望行为"是规则推演结果，不是人工标注。
3. **不把模板集合当覆盖度证明**。300 条只证明 5 个边界族各有 60 条可复算样本，不证明覆盖真实客服问句分布。

## 4. 复现

```bash
python3 scripts/make_dev.py --seed 20261103 --out /tmp/dev.jsonl
cmp data/dev.jsonl /tmp/dev.jsonl   # 必须无差异
python3 scripts/freeze.py --check   # 校验冻结快照与 manifest
```
