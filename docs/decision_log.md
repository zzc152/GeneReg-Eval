# Decision log inherited from the predecessor project

1. The project scope is regulatory DNA / gene regulation, not all biomedical knowledge.
2. The minimal record is evidence + regulator—relation—object + condition + provenance.
3. Regulator is not required to be a known TF; proteins, cofactors, perturbations and sequence elements may be in scope if textually supported.
4. Entity canonicalization (for example Gilda) is useful but deferred from the evidence-grounded MVP. Preserve raw mentions first.
5. Evidence may contain multiple sentences, but each span must be a verbatim abstract subset.
6. Relation normalization may reverse surface wording when the causal semantics justify it; do not confuse an intervention with the regulated factor. Example: knockdown of HNF4alpha decreasing PXR supports HNF4alpha activation of PXR, not HNF4alpha repression.
7. Hard rejection should be limited to deterministic defects: irreparable JSON, evidence absent from abstract, required entity absent from evidence, and demonstrable direction reversal. Uncertain semantics normally route to REVIEW.
8. Object-boundary loss is scientifically material: promoter/enhancer/motif/binding-site objects cannot be collapsed into bare genes.

