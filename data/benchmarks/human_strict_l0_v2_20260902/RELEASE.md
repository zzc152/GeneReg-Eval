# Human strict L0 benchmark v2

这是 GeneReg-Eval 的冻结 Human / PubMed 标题与摘要 / Level-0 分类基准：
`human_strict_l0_v2_20260902`。它保留 v1 的 267 条严格样本，并新增 164 条独立抽样、人工审阅的 TRRUST Unknown 样本。

| 任务 | 标签 | 条数 |
|---|---|---:|
| `KNOWN_DIRECTION` | `Activation` / `Repression` | 171 |
| `UNKNOWN_RELATION_PRESENCE` | `REGULATION_PRESENT` / `NO_REGULATION` | 260 |
| 合计 | — | 431 |

每个样本对应一个独立 PMID。严格集排除 `ABSTRACT_PARTIAL`、未解决和未审阅记录；它们不会被重标为负例。模型输入只包含标题、摘要与 regulator–target 候选查询，**不包含** TRRUST MoR 或人工 gold 标签。

```text
strict_records.jsonl                         冻结的 431 条 strict L0 记录
sources/article_records.jsonl                严格集对应的文章标题与摘要
opencompass/                                 171 道方向题与 260 道关系存在性题
manifest.json                                构建来源、任务组成与 SHA-256
reports/*_stats.json                         四个模型的汇总指标
reports/*_cases.jsonl                        每题完整输入、模型输出、预测与对错标记
```
