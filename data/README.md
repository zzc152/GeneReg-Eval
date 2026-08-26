# Data layout and provenance

Large source data is not copied into this scaffold. The first migration task is to create versioned manifests pointing to immutable source files in the predecessor repository or remote storage.

```text
data/
  manifests/       # PMID, species, TRRUST relation, source file hashes
  raw/             # downloaded PubMed records; never edit in place
  intermediate/    # parser / validator output
  gold/            # independent human or human-assisted labels
  sft/             # GeneReg-SFT records
  benchmark/       # frozen Level 1/2/3 splits and predictions
```

## Existing migration candidates

| Asset | Prior location | Notes |
|---|---|---|
| TRRUST human raw table | `TRRUST/srcfiles/trrust_rawdata.human.tsv` | Relation candidate source |
| TRRUST mouse raw table | `TRRUST/srcfiles/trrust_rawdata.mouse.tsv` | Required for cross-species work |
| Human PubMed abstracts | `data/trrust/trrust_human_pubmed_abstracts_v1.jsonl` | 6,554 records downloaded; 7 missing |
| 100-abstract human-assisted dev gold | `data/samples/trrust_human_human_assisted_gold_v3_100_20260823.jsonl` | Development only; not final test |
| 100-abstract extraction output | `data/processed/trrust_human_blind_extractions_100_v1_20260823.jsonl` | Blind model output |

Before copying, record SHA-256 and source revision in a manifest. Do not accidentally train on a held-out evaluation PMID.

