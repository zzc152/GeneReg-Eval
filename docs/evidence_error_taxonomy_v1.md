# Phase 3 Evidence Error Taxonomy v1

This taxonomy records why an adjudication/model decision diverges from Phase 3 policy. A code may describe a model error, a source limitation, or a TRRUST–abstract alignment issue; `error_scope` must distinguish these (`MODEL`, `SOURCE`, `ALIGNMENT`, or `HUMAN_POLICY`).

| Code | Scope | Definition |
|---|---|---|
| `UNKNOWN_MOR_MISINTERPRETATION` | MODEL/HUMAN_POLICY | Treating a directed abstract result as inconsistent merely because TRRUST MoR is Unknown. |
| `BINDING_ONLY_AS_REGULATION` | MODEL | Promoting ChIP/EMSA/occupancy/motif evidence alone to complete functional regulation. |
| `FUNCTIONAL_EVIDENCE_UNDERVALUED` | MODEL | Downgrading explicit perturbation, promoter, reporter, or combined binding-functional evidence despite a supported relation. |
| `BINDING_PLUS_FUNCTIONAL_EFFECT_MISCLASSIFIED_AS_BINDING_ONLY` | MODEL | Seeing binding but ignoring the linked directional expression/promoter consequence. |
| `DIRECTNESS_REQUIREMENT_TOO_STRICT` | MODEL | Requiring a fully direct molecular mechanism when functional transcriptional regulation is already established. |
| `PPI_NOT_TRANSCRIPTIONAL_REGULATION` | MODEL | Treating TF–Target protein interaction as Target-gene transcriptional regulation. |
| `POST_TRANSLATIONAL_NOT_TRANSCRIPTIONAL` | MODEL | Treating a protein modification/stability effect as transcriptional regulation. |
| `SPECIES_MISMATCH` | ALIGNMENT | Applying functional evidence from one species to a candidate in another species. |
| `SPECIES_SPECIFIC_FUNCTIONAL_EVIDENCE_MISMATCH` | ALIGNMENT | Abstract provides a species-specific functional result that does not support the candidate species. |
| `ORTHOLOG_NOT_ENTITY_MATCH` | ALIGNMENT | Treating an orthologue/paralogue as the supplied entity without explicit mapping. |
| `FAMILY_TO_SPECIFIC_TF` | ALIGNMENT | Assigning family- or complex-level evidence to one specific TRRUST TF without support. |
| `ENTITY_ALIAS_NORMALIZATION_FAILURE` | MODEL/ALIGNMENT | Failing to align an allowed symbol, old name, protein name, or alias to the supplied entity. |
| `ENTITY_IDENTITY_REVIEW` | ALIGNMENT | Text identity remains ambiguous even after the allowed mapping; requires review rather than forced alignment. |
| `PERTURBATION_DIRECTION_REVERSAL` | MODEL | Misreading intervention direction, e.g. knockdown-induced Target increase as activation. |
| `EDGE_DIRECTION_REVERSED` | ALIGNMENT | Abstract supports the reverse causal edge rather than supplied TF → Target. |
| `COOPERATIVE_REGULATION_TOO_STRICT` | MODEL | Rejecting explicit cooperative regulation merely because the named TF is not shown acting alone. |
| `OVERSTRICT_SINGLE_FACTOR_ATTRIBUTION` | MODEL | Rejecting a named TF's supported role in a functionally defined multi-factor regulatory complex because it lacks a separate perturbation. |
| `UPSTREAM_MEDIATOR_CONFUSION` | MODEL | Treating an upstream stimulus/mediator as invalidating an explicitly stated downstream TF → Target relation. |
| `INTRA_ABSTRACT_MOR_CONFLICT` | SOURCE | Explicitly conflicting directions occur within one abstract; preserve context and flag review. |
| `CONTEXT_DEPENDENT_MOR` | ALIGNMENT | Direction differs across explicit biological contexts rather than constituting a global contradiction. |
| `MOR_CONTRADICTION` | ALIGNMENT | Explicit functional evidence supports the opposite known TRRUST MoR for aligned entities/species/context. |
| `BAD_EVIDENCE_SPAN` | MODEL/HUMAN_POLICY | Decision may be correct but quoted span is non-continuous, non-source, or not sufficient in context. |
| `IGNORED_DIFFERENTIAL_EXPRESSION_CONTEXT` | MODEL | Model ignores functional expression/perturbation context and treats evidence as binding-only. |
| `CHROMATIN_ASSOCIATION_WITHOUT_TARGET_TRANSCRIPTION` | SOURCE/ALIGNMENT | TF-linked promoter/chromatin change is reported, but Target transcription/expression consequence is not established. |

## Annotation use

Apply zero or more codes only after a support-status adjudication. Preserve the source quote and a concise rationale. Do not use taxonomy codes to silently change a human label; policy-driven relabeling must create a new versioned human-review artifact.
