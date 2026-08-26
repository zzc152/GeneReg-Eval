# Evaluation protocol

## Splits and leakage prevention

Within each species, split on connected units rather than individual rows:

1. no PMID can appear in more than one split;
2. no exact `(regulator, target, relation)` can cross splits;
3. after alias normalization is introduced, connected components sharing a relation or PMID must remain together;
4. freeze test predictions before inspecting test errors.

The existing 100-abstract human set is a **development set** because its errors informed prompt and validator design. It cannot be presented as a final held-out score.

## Level 1 metrics

Report separate metrics rather than one misleading aggregate:

| Metric | Meaning |
|---|---|
| Evidence grounding precision | accepted records whose evidence and mentions are source anchored |
| Relation precision / recall / F1 | normalized relation agreement on `ABSTRACT_SUPPORTED` records |
| AUTO_ACCEPT faithful precision | fraction of automatic admissions judged faithful |
| Empty-output precision | fraction of model-empty abstracts independently judged to contain no extractable relation |
| Empty-output false-omission rate | fraction of model-empty abstracts judged to contain an extractable relation |
| Route confusion matrix | AUTO_ACCEPT / REVIEW / REJECT versus adjudicated route |

Never report TRRUST raw string match as biological extraction accuracy; aliases and granularity differ.

## Level 2

Evaluate both extraction and explanation:

- correct relation under evidence;
- observation-span grounding;
- rule selection correctness;
- abstention when evidence is insufficient;
- de-entityized variants, with lexical leakage checks.

## Cross-species

Human→Mouse means train/develop on human and evaluate only on a mouse test manifest with no shared PMID. This measures transfer, not a pooled score.

