# GeneReg-Eval

> 中文说明请见 [README.zh-CN.md](README.zh-CN.md)。

GeneReg-Eval is an evidence-grounded benchmark for assessing whether language
models can read a PubMed title and abstract and make a narrowly defined gene
regulation judgment. It separates a curated TRRUST candidate relation, the
abstract text, model output, and human adjudication; these are never treated as
interchangeable facts.

## Released benchmark: Human strict L0 v2

`human_strict_l0_v2_20260902` is a frozen, independently reviewed Human
held-out benchmark of **431 distinct PMID-linked abstracts**. The model sees
only the title, abstract, and candidate regulator/target query. It never sees
the TRRUST mode of regulation or the human label.

| Task | Question | Labels | Items |
|---|---|---|---:|
| `KNOWN_DIRECTION` | What direction is supported for this pair? | `Activation`, `Repression` | 171 |
| `UNKNOWN_RELATION_PRESENCE` | Is a transcriptional regulatory relationship supported? | `REGULATION_PRESENT`, `NO_REGULATION` | 260 |

The benchmark deliberately excludes `ABSTRACT_PARTIAL`, unresolved, and
unreviewed records rather than relabelling them as negatives. It retains the
v1 strict set and adds an independently reviewed TRRUST-Unknown reserve.

The release is under
[`data/benchmarks/human_strict_l0_v2_20260902`](data/benchmarks/human_strict_l0_v2_20260902).
It contains frozen source reviews, strict records, OpenCompass-ready MCQ files,
and result summaries. See its [release notes](data/benchmarks/human_strict_l0_v2_20260902/RELEASE.md)
for provenance and checksums.

## Baseline result

All four models answered the exact same 431 questions with deterministic decoding.

| Model | Overall | Direction | Relation presence |
|---|---:|---:|---:|
| Qwen2.5-7B-Instruct | 79.81% (344/431) | 81.29% (139/171) | 78.85% (205/260) |
| Qwen2.5-32B-AWQ | 84.92% (366/431) | 89.47% (153/171) | 81.92% (213/260) |
| Llama-3.3-70B-Instruct-AWQ | 84.69% (365/431) | **90.64% (155/171)** | 80.77% (210/260) |
| Mistral-Small-3.1-24B-Instruct | **85.61% (369/431)** | 88.30% (151/171) | **83.85% (218/260)** |

Full per-item inputs, raw outputs, parsed predictions, and correctness markers
for all four models are released under the v2 benchmark's `reports/` directory.
These results compare different architectures, sizes, quantization variants,
and inference backends; they do not isolate scale as the sole causal factor.

## Reproduce the benchmark materialization

All project execution is designed for the configured remote Linux server. The
scripts themselves are path-portable: set `GENEREG_EVAL_ROOT` when the checkout
is not the current working directory. Commands below are illustrative; they do
not download models or start vLLM.

```bash
export GENEREG_EVAL_ROOT=/workspace/zzc/GeneReg-Eval
cd "$GENEREG_EVAL_ROOT"
PYTHON=/workspace/zzc/envs/project_800/bin/python

# Rebuild strict labels from the frozen reviewed and resolution sources.
# Use new output names; the release artifacts are immutable.
$PYTHON scripts/review/build_human_heldout_strict_benchmark_v1.py \
  --reviewed data/benchmarks/human_strict_l0_v1_20260901/sources/reviewed_source.json \
  --resolved data/benchmarks/human_strict_l0_v1_20260901/sources/uncertain_resolved_source.json \
  --merged-output data/intermediate/example_merged.jsonl \
  --benchmark-output data/intermediate/example_strict.jsonl \
  --stats-output data/intermediate/example_stats.json

# Materialize deterministic OpenCompass questions from the rebuilt strict file.
$PYTHON scripts/review/build_opencompass_human_strict_l0_v1.py \
  --strict data/intermediate/example_strict.jsonl \
  --frozen-source data/benchmarks/human_strict_l0_v1_20260901/sources/article_records.jsonl \
  --output-dir data/intermediate/example_opencompass_l0
```

The benchmark generator deterministically counterbalances A/B option positions
per item.

OpenCompass configurations are in [`configs/opencompass`](configs/opencompass).
The 32B AWQ evaluation uses vLLM, while the 7B configuration uses the local
Hugging Face backend. Evaluate with OpenCompass in its own environment; exact
server-specific model paths are intentionally supplied through configuration or
environment rather than assumed by the data release.

## Analysis and reporting

- [`scripts/analysis/summarize_opencompass_l0_v1.py`](scripts/analysis/summarize_opencompass_l0_v1.py): label-level summaries.
- [`scripts/analysis/compare_opencompass_l0_paired_v1.py`](scripts/analysis/compare_opencompass_l0_paired_v1.py): paired transitions, exact McNemar, and paired bootstrap CI.
- [`docs/evaluation_protocol.md`](docs/evaluation_protocol.md): split, leakage, and metric rules.
- [`docs/evidence_error_taxonomy_v1.md`](docs/evidence_error_taxonomy_v1.md): evidence-grounding failure taxonomy.
- [`docs/phase3_gold_adjudication_spec_v1.md`](docs/phase3_gold_adjudication_spec_v1.md): human adjudication policy.

The paired-analysis release includes the 37 disagreement cases with full
question text, labels, and both predictions, enabling qualitative error
analysis without reconstructing model output.

## Scope and limitations

- This release is Human / abstract-only / Level-0 classification. It is not a
  full-text benchmark and does not establish biological truth beyond the
  abstract evidence policy.
- The 100-abstract development set that informed prompts and validators is not
  used for this held-out score.
- `NO_REGULATION` has only 16 items; its 32B recall estimate should be treated
  cautiously.
- Mouse alignment, Human-to-Mouse transfer, Level-2 reasoning evaluation, and
  Level-3 cross-document reasoning remain future work.

## Repository layout

```text
data/benchmarks/    frozen public benchmark releases
schemas/            record, SFT, and teacher-reasoning contracts
scripts/review/     audit ingestion, benchmark construction, validators
scripts/analysis/   metric and paired-comparison utilities
configs/opencompass/ evaluation configurations
docs/               protocol, architecture, adjudication, taxonomy
```

## Citation

This is an early benchmark release. If you use it, cite the repository commit
and benchmark version `human_strict_l0_v2_20260902`; also cite TRRUST and the
underlying PubMed records identified by the released PMIDs.
