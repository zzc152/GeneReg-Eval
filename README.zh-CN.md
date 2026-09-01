# GeneReg-Eval

GeneReg-Eval 是一个以文献证据为边界的基因调控 benchmark。模型只能基于 PubMed 标题、摘要和给定 regulator–target 候选对作答；TRRUST 方向标签和人工 gold 不会出现在模型输入中。

## Human strict L0 v1

冻结版本 `human_strict_l0_v1_20260901` 包含 **267 条独立 PMID 摘要**，来自 400 条独立人工审阅样本。`ABSTRACT_PARTIAL`、未解决和未审阅条目被排除，而非重标为负例。

| 任务 | 标签 | 样本数 |
|---|---|---:|
| `KNOWN_DIRECTION` | `Activation` / `Repression` | 171 |
| `UNKNOWN_RELATION_PRESENCE` | `REGULATION_PRESENT` / `NO_REGULATION` | 96 |

数据、人工审阅来源、strict records、OpenCompass 题目、模型结果和完整哈希说明位于 [`data/benchmarks/human_strict_l0_v1_20260901`](data/benchmarks/human_strict_l0_v1_20260901)。

## Baseline

| 模型 | 总体准确率 | 方向判断 | 调控存在性 |
|---|---:|---:|---:|
| Qwen2.5-7B-Instruct | 79.40% (212/267) | 81.29% | 76.04% |
| Qwen2.5-32B-AWQ | **90.26% (241/267)** | **91.23%** | **88.54%** |

同一批 267 题的配对比较中，32B 有 33 条 `7B wrong -> 32B correct`，有 4 条 `7B correct -> 32B wrong`，净提升 **10.86 个百分点**。精确双侧 McNemar `p = 1.08e-6`；20,000 次 paired bootstrap 的 95% CI 为 **+6.74 至 +15.36 个百分点**。

这项比较同时改变模型规模和量化方式，不能把结果严格归因于模型规模本身。

## 重建

项目在远程 Linux 环境执行。构造脚本可通过 `GENEREG_EVAL_ROOT` 指定项目根目录，且拒绝覆盖冻结发布物：

```bash
export GENEREG_EVAL_ROOT=/workspace/zzc/GeneReg-Eval
PYTHON=/workspace/zzc/envs/project_800/bin/python

$PYTHON scripts/review/build_human_heldout_strict_benchmark_v1.py \
  --reviewed data/benchmarks/human_strict_l0_v1_20260901/sources/reviewed_source.json \
  --resolved data/benchmarks/human_strict_l0_v1_20260901/sources/uncertain_resolved_source.json \
  --merged-output data/intermediate/example_merged.jsonl \
  --benchmark-output data/intermediate/example_strict.jsonl \
  --stats-output data/intermediate/example_stats.json

$PYTHON scripts/review/build_opencompass_human_strict_l0_v1.py \
  --strict data/intermediate/example_strict.jsonl \
  --frozen-source data/benchmarks/human_strict_l0_v1_20260901/sources/article_records.jsonl \
  --output-dir data/intermediate/example_opencompass_l0
```

重建已在远程验证：267 条 strict records、171 条方向题和 96 条存在性题均与冻结版本 SHA-256 一致。

## 分析工具与范围

- `scripts/analysis/summarize_opencompass_l0_v1.py`：标签级汇总。
- `scripts/analysis/compare_opencompass_l0_paired_v1.py`：配对转移、精确 McNemar、paired bootstrap。
- `docs/evaluation_protocol.md`：切分、泄漏控制和指标规则。
- `docs/evidence_error_taxonomy_v1.md`：证据边界错误 taxonomy。

当前版本是 Human / abstract-only / Level-0 benchmark；Mouse、Human→Mouse、Level-2 reasoning 与跨文献 Level-3 尚未发布。`NO_REGULATION` 仅有 16 条，相关结果应谨慎解释。
