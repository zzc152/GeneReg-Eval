# GeneReg-Eval

GeneReg-Eval 是一个面向生命科学语言模型的**基因调控关系抽取与证据推理**项目。

它以 TRRUST 的人工整理关系为外部关系参考，以关联 PMID 的 PubMed 摘要为独立证据来源，评测模型能否从文献中抽取并解释受证据约束的调控关系。

## 核心问题

> 显式、可核查的文献证据推理监督，能否让较小模型从实验观察中推导基因调控关系，而非只记忆关系表？

## 资源与任务

| 资源 / 任务 | 状态 |
|---|---|
| TRRUST human PMID 对齐与 PubMed 摘要下载 | 已在前序项目完成 |
| 100 篇 TRRUST-human 摘要开发集与人工辅助 gold | 已完成，**仅限开发用途** |
| 基于摘要的证据约束关系抽取 | 已有可迁移 prompt / parser / validator 原型 |
| GeneReg-SFT 训练集 | 待构建 |
| GeneReg-Eval Level 1 / 2 benchmark | 待构建 |
| Mouse 摘要对齐与 Human→Mouse 泛化集 | 待构建 |
| 跨文献 Level 3 | 后续扩展，不是当前 MVP |

## 三个评测层级

- **Level 1：关系抽取**：从摘要抽取 regulator、object、Activation / Repression / Unknown、证据及条件。
- **Level 2：证据推理**：将实验观察映射为简短、可核查的 inference rules；包括实体去标识化测试。
- **Level 3：跨文献推理**：少量 A→B→C 路径、上下文一致性与证据不足拒答。该层级延后。

## 最重要的边界

1. **TRRUST relation gold 不等于摘要支持 gold。** TRRUST 指出候选关系和 PMID；是否被该摘要独立支持必须另行标注。
2. 不训练或评测“普适生物学真理”；每条记录只主张其 evidence spans 明确支持的内容与条件。
3. 调控对象可为基因、promoter、enhancer、motif、binding site 或蛋白。不得把 `X promoter` 静默缩写为裸 `X`。
4. 结构化 reasoning 是可审计的 observation 与 rule，不收集冗长自由式思维链。

详细设计见 [docs/architecture.md](docs/architecture.md)、[docs/evaluation_protocol.md](docs/evaluation_protocol.md)。

## 当前优先顺序

1. 冻结并迁移 human 开发集；建立独立的 held-out test 集。
2. 构建 `ABSTRACT_SUPPORTED` 筛选与最小证据标注流程。
3. 先完成 Level 1 baseline 与 prompt 改进，再生成 Level 2 SFT 数据。
4. 最后做 Human→Mouse 和 Level 3。

