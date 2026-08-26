# Architecture

## Four distinct facts

```text
TRRUST relation candidate
        ≠
PubMed abstract evidence
        ≠
Model prediction
        ≠
Human / human-assisted adjudication
```

The project must store all four rather than overwrite one with another.

## Relation record

`schemas/gene_reg_record_v1.json` is the Level 1 output contract.

- `evidence_spans` may contain multiple non-contiguous source sentences.
- Every evidence span, regulator mention, object mention, and individual context mention must be a literal substring of the abstract.
- `relation` is semantic normalization and need not be literal text. Example: “HNF4alpha knock-down caused PXR decrease” can support normalized `HNF4alpha — Activation → PXR` only when the causal interpretation is explicit.
- A relation to `AF1 promoter` must retain `AF1 promoter` with `object_kind=regulatory_element`; it may not silently become an `AF1` gene record.

## ABSTRACT_SUPPORTED gate

Only records labeled `ABSTRACT_SUPPORTED` are eligible for Level 1 gold or GeneReg-SFT.

`ABSTRACT_UNSUPPORTED` is still useful for rejection and empty-output evaluation. `ABSTRACT_AMBIGUOUS` is retained for audit but excluded from main score denominators unless the protocol explicitly says otherwise.

## GeneReg-SFT

Teacher-generated supervision must be bounded and auditable:

```json
{
  "observations": [
    {"evidence_span": "...", "observation": "EPAS1 binds a site upstream of the Flt-1 promoter."}
  ],
  "inference_rules": [
    "Direct promoter binding plus reporter activation supports promoter activation in the stated context."],
  "answer": {"relation": "Activation", "object_mention": "Flt-1 promoter"}
}
```

Do not use unconstrained free-form chain-of-thought as a training target. Every observation must be source-grounded and every rule must be from a small, documented rule catalog.

