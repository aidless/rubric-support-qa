# 偏差日志（deviations）

> 结论先行：**本轮只新增里程碑 3 的文档与校验脚本，未修改任何已冻结文件。**
> S2 公示、S3 意见裁决、S4 签字、S5 判定翻转**均未完成**；本文件如实记录偏差与原因。

## 1. 冻结边界

| 项 | 状态 |
|---|---|
| `prereg.md` | 未修改（冻结，sha256 见 `data/manifest.json`） |
| `data/dev.jsonl` / `data/dev.frozen.jsonl` | 未修改 |
| `data/manifest.json` | 未重写（新增文件不属于冻结集） |
| `rubric/rubric.v0.yaml` | 未修改 |
| `rubric/counterexamples.jsonl` | 未修改 |
| `data/SOURCES.md` | 未修改 |

新增文件不进入 `manifest.json`：manifest 只固定"预注册 + dev 集 + v0 判据"这一组；需求/RFC/裁决/签字是过程记录，允许随公示更新。若后续修改上述冻结文件，必须新建版本并在此登记。

## 2. 本轮新增

| 文件 | 作用 | 状态 |
|---|---|---|
| `requirements.md` | S1：13 条带链接约束，映射到 9 个判据 | 完成（3 项目 / 13 条） |
| `RFC-001-rubric.md` | S2：需求→判据→失败后果 + 8 项拟议 diff | **草案，未公示** |
| `decisions.md` | S3：意见裁决表 | **空表，0 条意见** |
| `SIGNOFF.md` | S4：独立签字表 | **空表，0 人签字** |
| `scripts/check_requirements.py` | 需求文档结构与映射的机器校验 | 新增 |
| `tests/test_requirements.py` | 上述校验的单元测试 | 新增 |
| `README.md` | 状态表补里程碑 3 | 已更新 |

## 3. 与 PLAN.md 的偏差

| 编号 | PLAN 要求 | 实际 | 原因 | 影响 |
|---|---|---|---|---|
| D5-01 | 从 issue / FAQ / SLA 各提炼约束 | FastGPT 4 条（issue）、RAGFlow 4 条（issue + 官方 FAQ）、QAnything 3 条（1 条 issue + 2 条官方 API 文档） | QAnything 的知识库 API 文档提供了可核验的硬限制（2000 字符）与凭据范围，比 issue 更强 | 来源类型略宽于"issue/FAQ/SLA"，但全部为官方或一手 issue；不影响"≥3 项目、≥8 条"判据 |
| D5-02 | 每条判据应有需求来源 | `L2.compliance` 无外部来源 | 已核验的三个项目未公开讨论"客服话术合规" | 在 `requirements.md` 中显式声明为"作者判断"；不声称有来源 |
| D5-03 | S2 公示满 7 天、≥5 条意见 | 0 天、0 条 | 公示/联系维护者需用户逐次授权；本轮未获授权 | S2 未达成；`decisions.md` 如实为空 |
| D5-04 | S3 ≥3 条意见改变最终判定 | 0 条 | 依赖 S2 | 未达成 |
| D5-05 | S4 ≥2 名非作者签字 | 0 人 | 依赖 S2/S3 | 未达成 |
| D5-06 | S5 rubric v1 vs v2 判定翻转 ≥10 或 κ 提升 ≥0.10 | 未开始 | 依赖 S3；且需要 120 条分歧集，尚未构建 | 未达成；RFC §5 只写预期方向，不写实测 |
| D5-07 | `rubric.v1.yaml` 落地 | 未创建 | 变更仍在 RFC 讨论阶段；冻结 v0 不动 | 没有 v1 文件，避免"未评审先冻结" |

## 4. 证据强度说明

| 等级 | 条数 | 说明 |
|---|---|---|
| 直接 | 10 | issue 标题/正文或官方文档原文直接陈述约束 |
| 间接 | 2 | REQ-RF-04（部署侧数据外传）、REQ-QA-03（平台凭据边界）比判据更宽，仅支撑同一原则 |
| 标题级 | 1 | REQ-RF-05 只取到 RAGFlow FAQ 标题，正文抓取被截断 |

标题级证据不得在对外材料中写成"官方明确说明"。

## 5. 复核命令

```bash
cd ~/rubric-support-qa
python3 scripts/check_requirements.py --requirements requirements.md --rubric rubric/rubric.v0.yaml
python3 rubric/lint.py --rubric rubric/rubric.v0.yaml --counterexamples rubric/counterexamples.jsonl
python3 scripts/freeze.py --check
python3 -m unittest discover -s tests
```

前三项通过只代表文档结构、rubric 结构与冻结哈希一致；**不代表需求被认可、RFC 被采纳或 rubric 有效**。

## 6. 变更记录

| 日期 | 变更 | 影响 |
|---|---|---|
| 2026-11-03 | 新增 requirements / RFC-001 / decisions / SIGNOFF / 本文件 / 校验脚本 | 冻结文件零改动；S2–S5 未完成 |
