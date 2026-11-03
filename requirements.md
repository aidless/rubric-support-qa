# 真实需求来源（S1）

> 结论先行：**从 3 个真实开源项目（FastGPT、RAGFlow、QAnything）核验到 13 条可点击的硬约束，全部映射到 rubric 判据。**
> 其中 10 条为直接证据，2 条为间接证据（部署侧数据外传、平台凭据边界），1 条为标题级证据。
> 所有链接访问日期均为 **2026-11-03**；核验方式分为 `GitHub API` 与 `官方文档`。
> **本文件不代表已获得维护者认可**；S2 公开 RFC、S3 意见裁决、S4 独立签字均未开始。

## 核验口径

| 项 | 规则 |
|---|---|
| 来源数量 | 3 个项目（FastGPT / RAGFlow / QAnything） |
| 约束数量 | 13 条（PLAN 要求 ≥8 条） |
| 单条必备字段 | 链接、原文短引、访问日期、核验方式、主判据、产品后果、置信等级 |
| 置信等级 | `直接` = 原文直接陈述该约束；`间接` = 原文约束比判据更宽，仅支撑同一原则；`标题级` = 只取到标题，正文未取到 |
| 未声称 | 不声称这些 issue 已被维护者采纳，也不声称本 rubric 能代表全部用户需求 |

## 约束清单

| ID | 项目 | 硬约束 | 来源 | 原文/短引 | 访问日期 | 核验方式 | 主判据 | 不满足的产品后果 | 置信 |
|---|---|---|---|---|---|---|---|---|---|
| REQ-FG-01 | FastGPT | 答案须能关联到具体文档及位置 | [FastGPT #359](https://github.com/labring/FastGPT/issues/359) | "Can the answer be associated with the specific source (location) of the document when asking questions in the knowledge base?" | 2026-11-03 | GitHub API | L1.grounding | 用户无法核验回答，错误信息被当成结论 | 直接 |
| REQ-FG-02 | FastGPT | 知识库匹配不到时不得给出不准确答案 | [FastGPT #587](https://github.com/labring/FastGPT/issues/587) | "The answer is inaccurate and cannot be matched in the knowledge base." | 2026-11-03 | GitHub API | L1.must_refuse | 检索未命中仍作答，产生编造内容 | 直接 |
| REQ-FG-03 | FastGPT | citation 必须可用于答案溯源 | [FastGPT #1406](https://github.com/labring/FastGPT/issues/1406) | "如何对citation进行答案溯源???" | 2026-11-03 | GitHub API | L1.grounding | 引用只是装饰，用户不能定位依据 | 直接 |
| REQ-FG-04 | FastGPT | 非知识库问答也须带引用 | [FastGPT #1446](https://github.com/labring/FastGPT/issues/1446) | "非知识库问答添加引用" | 2026-11-03 | GitHub API | L2.faithful | 无检索场景下模型自由发挥，无法核对 | 直接 |
| REQ-FG-05 | FastGPT | 溯源须精确到段落位置并可跳转 | [FastGPT #4094](https://github.com/labring/FastGPT/issues/4094) | "用户经常会希望知道AI回答的内容具体来源于那个文档的什么位置"；"点击标签后，会打开对应的文档，并跳转到对应的段落位置" | 2026-11-03 | GitHub API | L2.actionable | 只给文档名，用户仍需自行翻找全文 | 直接 |
| REQ-RF-01 | RAGFlow | 可溯源回答与 citations 是产品核心能力 | [RAGFlow FAQ](https://ragflow.io/docs/faq) | "Flexible retrieval and traceable answers with multiple retrieval strategies, reranking, and citations." | 2026-11-03 | 官方文档 | L1.grounding | 产品对外承诺落空，溯源不可用 | 直接 |
| REQ-RF-02 | RAGFlow | 引用必须能定位到原始文件 | [RAGFlow #12532](https://github.com/infiniflow/ragflow/issues/12532) | "citations in the anwser can not jump into the origin file"（原文拼写如此） | 2026-11-03 | GitHub API | L2.actionable | 引用不可点击，用户无法回到原文 | 直接 |
| REQ-RF-03 | RAGFlow | 答案与引用条目必须一致 | [RAGFlow #7232](https://github.com/infiniflow/ragflow/issues/7232) | "The answer and the citation do not match" | 2026-11-03 | GitHub API | L2.faithful | 引错来源，用户被误导 | 直接 |
| REQ-RF-04 | RAGFlow | 用户上传数据不得外传或泄露 | [RAGFlow #6261](https://github.com/infiniflow/ragflow/issues/6261) | "If I upload files to RAGFlow, will the files interact with external networks or be transmitted to the cloud/public internet? I have to avoid data leakage" | 2026-11-03 | GitHub API | L1.pii | 隐私与合规风险，用户不敢上传真实资料 | 间接 |
| REQ-RF-05 | RAGFlow | 资料中已有答案仍不得幻觉 | [RAGFlow FAQ](https://ragflow.io/docs/faq#why-can-the-model-still-hallucinate-when-the-answer-exists-in-the-dataset) | "Why can the model still hallucinate when the answer exists in the dataset?"（仅标题级，正文未取到） | 2026-11-03 | 官方文档 | L1.must_refuse | 明明有依据却编造，检索形同虚设 | 标题级 |
| REQ-QA-01 | QAnything | PDF 等非纯文本内容须被正确理解并覆盖 | [QAnything #463](https://github.com/netease-youdao/QAnything/issues/463) | "问知识库是pdf的内容，理解能力差" | 2026-11-03 | GitHub API | L2.complete | 漏读表格与版式条件，答非所问 | 直接 |
| REQ-QA-02 | QAnything | FAQ 答案长度须不超过 2000 字符 | [QAnything 知识库 API](https://ai.youdao.com/qanything/docs/api/dataset) | "answer"，"长度不超过2000字符（必填）" | 2026-11-03 | 官方文档 | L2.clarity | 超出平台限制无法入库，答案被截断或拒绝 | 直接 |
| REQ-QA-03 | QAnything | 问答凭据只能用于其所属 Agent | [QAnything API 简介](https://ai.youdao.com/qanything/docs/intro/api-intro) | "问答秘钥只能用于密钥所属Agent的相关调用" | 2026-11-03 | 官方文档 | L1.authority | 越权调用其他 Agent，造成越界承诺或数据越权 | 间接 |

## 无外部来源的判据（作者判断）

以下判据在已核验的 3 个项目中**没有找到直接对应**的公开 issue 或文档。保留它们属于场景内在要求，但必须在 RFC 公示期优先征集来源；若仍无来源，报告中如实标注"作者判断"。

| 判据 | 为什么保留 | 拟议处理 |
|---|---|---|
| L2.compliance | "客服口径符合平台规则、不夸大"是客服场景的固有要求；三个开源 RAG 项目的公开 issue 更多聚焦溯源与拒答，未直接讨论客服话术合规 | 保留在 v1；在 RFC §7 中列为优先征集意见的问题；不声称有外部来源 |

## 覆盖统计

| 判据 | 覆盖需求 | 证据强度 |
|---|---|---|
| L1.pii | REQ-RF-04 | 间接 |
| L1.grounding | REQ-FG-01、REQ-FG-03、REQ-RF-01 | 直接 |
| L1.authority | REQ-QA-03 | 间接 |
| L1.must_refuse | REQ-FG-02、REQ-RF-05 | 直接 + 标题级 |
| L2.complete | REQ-QA-01 | 直接 |
| L2.faithful | REQ-FG-04、REQ-RF-03 | 直接 |
| L2.compliance | 无（作者判断） | 无外部来源 |
| L2.actionable | REQ-FG-05、REQ-RF-02 | 直接 |
| L2.clarity | REQ-QA-02 | 直接 |

## 机器校验

```bash
python3 scripts/check_requirements.py \
  --requirements requirements.md \
  --rubric rubric/rubric.v0.yaml
```

校验项：≥3 个项目、≥8 条约束、ID 唯一、每条有 https 链接 / 访问日期 / 核验方式 / 合法 rubric id、引用非空、L1 与 L2 每个判据要么被覆盖要么在"作者判断"表中声明。

## 访问记录

| 日期 | 动作 | 结果 |
|---|---|---|
| 2026-11-03 | 通过 GitHub API 读取 FastGPT / RAGFlow / QAnything 的 issue 标题、正文与状态 | 取得 11 条 issue 证据；GitHub 网页直连被拦截，改用 API |
| 2026-11-03 | 抓取 RAGFlow FAQ 与 QAnything 知识库/API 简介文档 | 取得 2 条官方文档证据；RAGFlow 幻觉 FAQ 仅取到标题 |

**未做**：未联系任何维护者，未在 Discussions 发帖，未取得任何书面认可。
