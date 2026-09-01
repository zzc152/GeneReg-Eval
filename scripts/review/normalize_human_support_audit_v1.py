"""Preserve human support-audit annotations while separating non-source spans."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path("/workspace/zzc/GeneReg-Eval")


def source_contains(span: str, title: str, abstract: str) -> bool:
    return span in title or span in abstract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Human-review JSON array")
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats-output", required=True)
    parser.add_argument("--articles", default="data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl")
    args = parser.parse_args()
    output, stats_output = ROOT / args.output, ROOT / args.stats_output
    if output.exists() or stats_output.exists():
        raise SystemExit("Refusing to overwrite an existing normalized human-review artifact")
    with (ROOT / args.articles).open(encoding="utf-8") as handle:
        articles = {str(x["pmid"]): x for x in (json.loads(line) for line in handle if line.strip())}
    source_rows = json.loads((ROOT / args.input).read_text(encoding="utf-8"))
    if not isinstance(source_rows, list):
        raise SystemExit("Human-review input must be a JSON array")
    rows, routes = [], Counter()
    for source in source_rows:
        row = dict(source)
        pmid = str(row.get("pmid") or "")
        article = articles.get(pmid)
        if article is None:
            raise SystemExit(f"PMID not found in article cache: {pmid}")
        title, abstract = str(article.get("title") or ""), str(article.get("abstract") or "")
        decision = row.get("abstract_supported")
        entered = str(row.get("evidence_span") or "").strip()
        note = ""
        if not entered:
            route = "EMPTY"
            normalized_span = None
        elif decision != "YES":
            route = "TEXT_WITH_NON_SUPPORTED_DECISION"
            normalized_span = None
            note = f"Human-entered text under {decision or 'UNSET'} decision: {entered}"
        elif source_contains(entered, title, abstract):
            route = "CONTINUOUS_SOURCE"
            normalized_span = entered
        else:
            route = "NOT_CONTINUOUS_SOURCE"
            normalized_span = None
            note = f"Human-entered non-continuous/non-source span: {entered}"
        row["evidence_span_input"] = row.get("evidence_span") or None
        row["evidence_span"] = normalized_span
        row["review_note"] = note or None
        row["span_validation_route"] = route
        rows.append(row)
        routes[route] += 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stats = {
        "artifact_type": "human_review_support_audit_normalized_v1",
        "input_records": len(rows),
        "decision_counts": dict(Counter(str(x.get("abstract_supported") or "UNSET") for x in rows)),
        "span_validation_counts": dict(routes),
        "preservation_rule": "Non-continuous spans and text entered under a non-supported decision are retained in review_note and removed from evidence_span.",
    }
    stats_output.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
