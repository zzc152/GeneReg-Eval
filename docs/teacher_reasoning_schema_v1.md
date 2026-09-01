# Teacher reasoning source schema v1

This contract is for the next Phase 3 output only: a strong teacher converts an already admitted `ABSTRACT_SUPPORTED` relation into a bounded chain:

```text
verbatim evidence -> experimental observation -> catalogued inference rule -> final relation
```

It is not a request for free-form chain-of-thought. The raw teacher object uses [gene_reg_teacher_reasoning_v1.json](../schemas/gene_reg_teacher_reasoning_v1.json). Its deterministic validation result is stored separately under [gene_reg_teacher_reasoning_validation_v1.json](../schemas/gene_reg_teacher_reasoning_validation_v1.json), so validation never mutates or disguises raw teacher output.

## Admission and provenance

Only an upstream record with all four gates may enter this schema:

- first pass: `ABSTRACT_SUPPORTED`;
- first validator: `VALID`;
- second pass: `PASS`;
- second validator: `VALID`.

`source_record_key`, PMID, species, title SHA-256, and abstract SHA-256 retain a stable link to the immutable PubMed cache. The teacher also receives the upstream relation and its admission support span as reference material.

The teacher must choose one of two explicit assessments:

- `AGREES_UPSTREAM`: emit `final_relation`, which must reproduce the upstream admitted relation exactly.
- `UPSTREAM_ERROR_SUSPECTED`: emit no replacement relation (`final_relation: null`), cite one or more teacher evidence IDs, and give a concise reason. The deterministic validator routes this to `REVIEW`; it never overwrites the upstream record or creates a new edge.

## Bounded components

- `evidence`: one to four literal title/abstract spans selected for the teacher's observation/rule chain. At least one must carry the functional relation. They may reference, expand beyond, or be entirely different from the upstream minimal support span; equality with that span is neither required nor desirable.
- `observations`: concise evidence-grounded restatements, each linked to one or more evidence IDs. They can describe an experimental observation or an explicit authorial assertion; they cannot contain a new mechanism. An assertion records whether it is a current-study result, prior-work assertion, or background assertion.
- `rule_applications`: one to four applications from the `GRR-001` through `GRR-010` catalog embedded in the schema. Each cites its observation IDs and yields only a normalized relation.
- `final_relation`: source-form entity mentions, normalized relation, referenced evidence/rules, `primary_rule_application_id`, and a structured six-field `relation_condition`. The primary rule is the highest-priority applicable rule; concrete functional evidence outranks a generic authorial assertion.
- `relation_condition`: answers only **“关系只在哪些条件下成立”** (“under which explicitly stated conditions does this relation hold?”). Every field is an array of zero or more literal source substrings linked to evidence. Include only information that directly constrains where, when, or under what setting the relation holds. Experimental interventions used merely to establish causality (for example TF/Target knockdown, overexpression, or mutation) are not conditions.

The current catalog is frozen in [gene_reg_inference_rule_catalog_v1.json](../schemas/gene_reg_inference_rule_catalog_v1.json). Its priority order is binding-site function; loss/gain perturbation direction; promoter/reporter function; binding plus function; named complex function; explicit assertion; then direction-unspecified fallback. It covers causal inference patterns rather than assay names. Functional evidence that cannot safely map to one of its rules is routed to `REVIEW`, not converted into a teacher-created rule.

The initial catalog covers explicit transcriptional statements, loss/gain perturbation direction, promoter/reporter function, binding plus functional effect, binding-site mutation, named functional complexes, and functional relations with unspecified direction. It deliberately does not treat binding, occupancy, correlation, PPI, or downstream protein abundance alone as sufficient rules.

## Automatic consistency checks

The sidecar validator must check:

1. JSON Schema validity and unique IDs/references;
2. source title/abstract SHA-256 match;
3. every evidence span and condition mention is a literal substring of the source;
4. evidence IDs cited by observations and final relation exist;
5. `inference_rule_catalog_version` equals the frozen v1 catalog, every rule ID is known, and every rule is compatible with its observation type;
6. for `AGREES_UPSTREAM`, final relation, source-form entity anchors, MoR, object boundary, and highest-priority primary rule match the admitted upstream record and applicable catalog;
7. for `UPSTREAM_ERROR_SUSPECTED`, `final_relation` is null, cited challenge evidence exists, and the record is routed to `REVIEW`.

Deterministic defects are `REJECT`; semantic uncertainty and teacher-raised upstream disagreement are `REVIEW`. Only agreed, `VALID` records are projected into the older `gene_reg_sft_v1` training view.

## Human audit

Sample after validation with strata for species, relation, rule ID, PMID age, evidence-count, and validator route. Oversample `REVIEW`, rare rules, multi-span chains, complexes/aliases, and records whose final relation relies on perturbation direction. Human review asks only whether each link is faithful: evidence -> observation, observation -> rule, and rule -> final relation.
