# Migration handoff from BioDesign-Agent

## What is reusable now

| Capability | Predecessor path | Migration action |
|---|---|---|
| TRRUST human PubMed downloader | `scripts/data/download_trrust_human_pubmed.py` | Copy/adapt after creating a manifest-based downloader |
| Blind extraction runner | `scripts/extract/run_trrust_human_v1.py` | Rename; do not retain `v1` labels or metadata |
| Prompt / parser / validator package | `src/trrust_human/` | Port only after reconciling its `tf_mention` name with `regulator_mention` |
| v2 evidence/context contract | `docs/trrust_human_assertion_v2.md`, `schemas/trrust_human_assertion_v2.schema.json` | Use as a reference, then adopt this repository's schema v1 |
| Validator replay | `scripts/analysis/revalidate_trrust_human_v2.py` | Generalize for named baseline/candidate versions |
| Human review HTML renderers | `scripts/analysis/create_trrust_human_*review_html.py` | Port as generic review UI; preserve bilingual requirement |
| Gold v3 evaluator | `scripts/analysis/evaluate_trrust_human_gold_v3.py` | Port metrics, but keep gold provenance explicit |

## Verified predecessor evidence

The predecessor's human-assisted gold v3 covers 100 TRRUST-human abstracts:

| Item | Value |
|---|---:|
| candidate-bearing abstracts | 70 |
| model-empty abstracts | 30 |
| model-empty abstracts judged to miss a relation | 21 |
| v2 AUTO_ACCEPT faithful precision on candidates | 93.1% |

Interpretation: validator hardening improved admission safety, but the next major bottleneck is extraction recall / prompt coverage. These are development findings, not held-out benchmark results.

## Required first migration commits

1. Copy source data with SHA-256 manifests; do not depend on relative paths to the predecessor project at runtime.
2. Rename schema fields from `tf_mention` to `regulator_mention` where the broader scope is intended.
3. Implement multi-span evidence as an array from the beginning.
4. Rebuild a fresh held-out human review sample before claiming benchmark performance.
5. Download and manifest mouse abstracts before designing cross-species splits.

