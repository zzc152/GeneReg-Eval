# Human strict L0 v1 (2026-09-01)

This directory is the frozen release of the first GeneReg-Eval held-out Human
benchmark. It is based on 400 independently sampled PubMed abstracts reviewed
at L0/L1. Strict L0 selection retains 267 records and does not turn partial or
unresolved cases into negatives.

## Files

```text
sources/reviewed_source.json                400 primary human-review records
sources/uncertain_resolved_source.json      later resolution overrides
sources/merged_review_records.jsonl         frozen post-override audit record set
sources/article_records.jsonl               article-bearing frozen source for MCQ materialization
strict_records.jsonl                        267 strict L0 records and L1 fields
opencompass/human_strict_l0_direction.jsonl 171 direction MCQs
opencompass/human_strict_l0_presence.jsonl  96 presence MCQs
opencompass/manifest.json                   prompt and option-position manifest
qwen25_7b_results.json                      7B label-level summary
qwen25_32b_awq_results.json                 32B label-level summary
reports/qwen25_7b_vs_32b_paired.json        paired statistics for both models
reports/qwen25_7b_vs_32b_transition_cases.json 37 full disagreement cases
```

The MCQ files are model inputs and therefore contain the title, abstract,
candidate query, A/B labels, and answer. They deliberately omit TRRUST MoR and
human adjudication text from the question prompt.

## Source policy

For known TRRUST `Activation`/`Repression` candidates, strict selection requires
human `ABSTRACT_SUPPORTED` plus an explicit human direction. For TRRUST
`Unknown` candidates, strict selection maps human `ABSTRACT_SUPPORTED` to
`REGULATION_PRESENT` and `ABSTRACT_INSUFFICIENT` to `NO_REGULATION`. It excludes
`ABSTRACT_PARTIAL`, unresolved records, and unreviewed records.

`sources/uncertain_resolved_source.json` has precedence over the corresponding
primary review record. The original audit source is retained rather than
silently overwritten.

## Integrity

The release hashes before repository reorganization were:

| Artifact | SHA-256 |
|---|---|
| strict records | `f93cc7b17d6519c291106b28021466177c6d0f0b4c64ca014981d3c8c46d30fd` |
| article-bearing source | `e3c52116e9bec57023f69ab11384cbfd77d0d4c445d17d18f92a7fbc2c625726` |
| direction MCQs | `982f8e3d0c865708f64d9a80c58f3860e936850fb93b3aa90bec86f3255b06db` |
| presence MCQs | `c7ad2bea2c412e627776beeb69b1bc2d0429ea6a9c76e93976c31a89624f750c` |
| OpenCompass manifest | `b04a4fdfaa013e45e6aa5df6a272abd1730f51ce4ef6f02e2ba96eb12e7d3e74` |

## Rebuilding derived files

`scripts/review/build_human_heldout_strict_benchmark_v1.py` builds the strict
records from the two JSON review sources. `scripts/review/build_opencompass_human_strict_l0_v1.py`
materializes the OpenCompass files from strict records and the article-bearing
frozen source (`sources/article_records.jsonl`). Both tools refuse to overwrite
an existing output, preserving release immutability.
