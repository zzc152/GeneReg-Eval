# Phase 3 Gold Adjudication Specification v1

## 1. Purpose and scope

This specification defines how to adjudicate whether a PubMed title/abstract independently supports an existing TRRUST TF → Target candidate. It does not discover new relations, alter TRRUST, or substitute for full-text curation.

The rule set was consolidated after the 100-record `human_review_benchmark_v1_20260828` and 36 adjudicated Qwen–human disagreements. The free-text adjudication note and cited abstract evidence take precedence over the page's quick adjudication dropdown. `BOTH_DEFENSIBLE` and `UNCERTAIN` are review states, never final Gold labels.

English title/abstract is the only evidence source. Chinese translations, TRRUST labels, aliases, and model memory are not evidence.

## 2. Required record fields

Each adjudicated record retains:

```text
TRRUST: tf, target, trrust_mor, species, PMID
Entity alignment: abstract_tf_mention, abstract_target_mention
Review: support_status, abstract_mor, trrust_alignment
Evidence: evidence_span, condition, review_flag, review_note
Quality: evidence_span_validation
```

`evidence_span` is one continuous, verbatim title/abstract fragment sufficient for the conclusion. It need not be unique or globally minimal.

## 3. Entity and source rules

1. The model/reviewer may use the supplied approved-symbol/alias mapping only to align a text mention to the supplied TRRUST entity.
2. Extracted entity strings must be copied from title/abstract, never normalized back to TRRUST notation.
3. A family, complex, paralogue, orthologue, fusion protein, or similarly named entity is not automatically the supplied TRRUST TF/Target.
4. If entity identity cannot be resolved, do not mark the candidate `ABSTRACT_SUPPORTED`; use `ABSTRACT_PARTIAL` or `ABSTRACT_INSUFFICIENT` as appropriate and set `trrust_alignment = ENTITY_UNRESOLVED`.
5. Evidence for a human relation does not independently support a mouse candidate, or conversely, unless the abstract explicitly establishes the relevant species-specific relation.

## 4. Support status

`support_status` answers only: *does this abstract independently support the supplied TRRUST candidate?*

### ABSTRACT_SUPPORTED

Use when title/abstract establishes the aligned TF, Target, and a functional transcriptional regulatory relationship. A fully direct molecular mechanism is not required; the functional evidence must nevertheless connect the TF/TF-containing regulatory complex to Target transcription, expression, or promoter activity.

For `trrust_mor = Activation` or `Repression`, the abstract must establish the corresponding direction. Valid patterns include:

- explicit `TF activates/represses/regulates Target` language;
- TF perturbation causing a directional Target expression or promoter-activity change;
- TF-specific binding-site perturbation causing Target promoter activity change;
- binding evidence combined with an explicit functional transcriptional consequence;
- explicit cooperative regulation where the named TRRUST TF is an identified component and the abstract ties that complex to Target transcription.

For `trrust_mor = Unknown`, direction is not required. A functional reporter, perturbation, expression, or explicit regulation statement is sufficient; an explicit direct mechanism is not additionally required. If the abstract explicitly establishes activation or repression, set `abstract_mor` to that direction and `trrust_alignment = MOR_MORE_SPECIFIC_THAN_TRRUST`.

### ABSTRACT_PARTIAL

Use when the abstract supports a relevant but incomplete fact, including:

- TF binding/occupancy at the Target promoter by ChIP, EMSA, footprinting, or motif analysis alone;
- chromatin/promoter modification associated with TF expression or binding, without evidence that Target transcription/expression changes;
- predicted motif or promoter occupancy without functional transcriptional consequence;
- a family/complex-level relationship that cannot be reliably assigned to the supplied TF;
- some functional relation where the direction required by a known TRRUST MoR cannot be established.

### ABSTRACT_INSUFFICIENT

Use when the abstract cannot establish the supplied transcriptional candidate, including:

- TF–Target protein interaction only;
- post-translational regulation only;
- correlation, co-expression, pathway co-occurrence, or independent co-mention;
- an edge in the reverse direction;
- incompatible species evidence;
- an unresolved or incompatible entity identity.

## 5. MoR and TRRUST alignment

`abstract_mor` is `Activation`, `Repression`, `Unknown`, or `null`. `trrust_alignment` preserves the relationship between abstract evidence and the candidate:

| Alignment | Use |
|---|---|
| `ALIGNED` | Abstract supports the relation and compatible MoR. |
| `MOR_MORE_SPECIFIC_THAN_TRRUST` | TRRUST MoR is Unknown; abstract establishes activation or repression. |
| `MOR_CONTRADICTION` | Same aligned entities/species/context have explicit functional evidence for the opposite known TRRUST MoR. |
| `EDGE_DIRECTION_REVERSED` | Abstract supports Target → TF or another reverse relation instead. |
| `SPECIES_MISMATCH` | Functional evidence is for a different species. |
| `ENTITY_UNRESOLVED` | Candidate entity cannot be reliably aligned. |
| `CONTEXT_DEPENDENT_MOR` | Different explicit contexts in the abstract yield different directions. |
| `NOT_ASSESSABLE` | Abstract does not permit a more specific alignment assessment. |

`MOR_CONTRADICTION` is an alignment flag, not a replacement support status. Because it does not support the supplied candidate, its `support_status` is normally `ABSTRACT_INSUFFICIENT`. Do not call a relation contradictory merely because TRRUST MoR is Unknown and the abstract gives a direction.

## 6. Evidence span, condition, and review flags

- A supported record must contain a non-empty continuous verbatim evidence span.
- A partial/insufficient record has `evidence_span = null`; explanatory quotations belong in `review_note`.
- A valid span need not repeat both entity strings if surrounding title/abstract establishes their referents. It must itself be continuous original text and sufficient in context for the stated conclusion.
- `condition` contains only directly stated relation-level constraints. It is optional and every populated value is a continuous source substring.
- `review_flag = true` for unresolved entity identity, species ambiguity, competing directions, inadequate source text, or another material adjudication uncertainty.

## 7. Calibration and versioning

The existing `human_review_benchmark_v1` remains an immutable record of its original YES/NO policy. Any relabeling under this specification must create `human_review_benchmark_v2` or later; never overwrite v1.

## 8. Adjudicated boundary precedents

These precedents summarize the reviewer notes used to resolve recurring disagreements:

- `HDAC4 → HDAC3` (PMID 11804585): protein/corepressor-complex interaction is `ABSTRACT_INSUFFICIENT`, not partial regulation, because no HDAC3 gene regulation is established.
- `Ascl1 → Hes5`, `Zbtb32 → Ciita`, and `Irf8 → Slc11a1`: a directed abstract result supports an `Unknown` TRRUST edge and receives `MOR_MORE_SPECIFIC_THAN_TRRUST`; it is not a contradiction.
- `NFKB1 → IL23A` and related cooperative cases: explicit placement of the named TF in a regulatory complex plus functional target-transcription evidence can support the edge without a single-factor perturbation.
- `Tcf3 → Nr0b2` and `Klf15 → Rbp3`: species-specific evidence must match the candidate species; an otherwise valid human/bovine promoter experiment does not independently establish a mouse edge.
- `Ets1 → Fli1`: opposing reporter and endogenous results within one abstract are `CONTEXT_DEPENDENT_MOR` with `review_flag = true`, not forced into one direction.

Before large-scale inference, build a small, deliberately selected Phase 3 Calibration Gold set covering all support statuses and the boundary cases in the accompanying Error Taxonomy.
