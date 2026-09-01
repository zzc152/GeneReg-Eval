"""Build a versioned benchmark and report from normalized human abstract audits."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/workspace/zzc/GeneReg-Eval")


def rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--sample", required=True)
    parser.add_argument("--articles", default="data/intermediate/trrust_pubmed_articles_v1_20260826.jsonl")
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats-output", required=True)
    parser.add_argument("--report-output", required=True)
    args = parser.parse_args()
    output, stats_output, report_output = ROOT / args.output, ROOT / args.stats_output, ROOT / args.report_output
    if any(path.exists() for path in (output, stats_output, report_output)):
        raise SystemExit("Refusing to overwrite an existing benchmark artifact")
    reviews = json.loads((ROOT / args.reviews).read_text(encoding="utf-8"))
    review_by_id = {str(x["sample_id"]): x for x in reviews}
    with (ROOT / args.articles).open(encoding="utf-8") as handle:
        articles = {str(x["pmid"]): x for x in (json.loads(line) for line in handle if line.strip())}
    benchmark = []
    with (ROOT / args.sample).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            sample = json.loads(line)
            review = review_by_id.get(sample["sample_id"])
            if review is None:
                raise SystemExit(f"Missing review for {sample['sample_id']}")
            article = articles[str(sample["pmid"])]
            yes = review.get("abstract_supported") == "YES"
            benchmark.append({
                "benchmark_id": sample["sample_id"],
                "label_provenance": "human_review",
                "audit_question": "Can this PubMed title/abstract independently support the supplied TRRUST relation?",
                "pmid": str(sample["pmid"]), "species": sample["stratum"]["species"],
                "trrust_tf": sample["tf_mention"], "trrust_target": sample["object_mention"], "trrust_mor": sample["relation"],
                "abstract_tf_mention": sample.get("tf_matched_candidate"), "abstract_target_mention": sample.get("target_matched_candidate"),
                "title": article.get("title"), "abstract": article.get("abstract"),
                "human_abstract_supported": yes,
                "human_evidence_span": review.get("evidence_span"),
                "human_review_note": review.get("review_note"),
                "span_validation_route": review.get("span_validation_route"),
                "evidence_span_input": review.get("evidence_span_input"),
            })
    by_stratum: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in benchmark:
        by_stratum[(row["species"], row["trrust_mor"])].append(row)
    strata = []
    for key in sorted(by_stratum):
        rows = by_stratum[key]
        supported = sum(x["human_abstract_supported"] for x in rows)
        clean_spans = sum(x["span_validation_route"] == "CONTINUOUS_SOURCE" for x in rows)
        notes = sum(bool(x["human_review_note"]) for x in rows)
        strata.append({"species": key[0], "mor": key[1], "records": len(rows), "supported": supported, "not_supported": len(rows)-supported, "support_rate": rate(supported, len(rows)), "continuous_evidence_spans": clean_spans, "records_with_notes": notes})
    routes = Counter(x["span_validation_route"] for x in benchmark)
    supported = sum(x["human_abstract_supported"] for x in benchmark)
    note_rows = [{"benchmark_id": x["benchmark_id"], "pmid": x["pmid"], "route": x["span_validation_route"], "note": x["human_review_note"]} for x in benchmark if x["human_review_note"]]
    stats = {
        "benchmark_version": "human_review_benchmark_v1_20260828",
        "label_provenance": "human_review",
        "records": len(benchmark), "supported": supported, "not_supported": len(benchmark)-supported, "support_rate": rate(supported, len(benchmark)),
        "continuous_evidence_spans": routes["CONTINUOUS_SOURCE"], "span_validation_counts": dict(sorted(routes.items())),
        "records_with_review_notes": len(note_rows), "strata": strata, "note_records": note_rows,
        "interpretation": "A not-supported label means this title/abstract did not independently support the supplied relation under this audit; it does not invalidate the TRRUST relation or its full-text evidence.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in benchmark) + "\n", encoding="utf-8")
    stats_output.parent.mkdir(parents=True, exist_ok=True)
    stats_output.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Human review benchmark v1", "",
        "Scope: independent support by the PubMed title/abstract for an existing TRRUST candidate. `NO` does not invalidate TRRUST or its full-text evidence.", "",
        "## Overall", "",
        f"- Records: {len(benchmark)}", f"- Human ABSTRACT_SUPPORTED: {supported} ({supported / len(benchmark):.1%})", f"- Human not supported: {len(benchmark)-supported} ({(len(benchmark)-supported) / len(benchmark):.1%})", f"- Continuous, source-anchored evidence spans: {routes['CONTINUOUS_SOURCE']}", f"- Records with preserved review notes: {len(note_rows)}", "",
        "## By species × TRRUST MoR", "", "| Species | MoR | Records | Supported | Support rate | Continuous spans | Notes |", "|---|---|---:|---:|---:|---:|---:|",
    ]
    lines += [f"| {x['species']} | {x['mor']} | {x['records']} | {x['supported']} | {x['support_rate']:.1%} | {x['continuous_evidence_spans']} | {x['records_with_notes']} |" for x in strata]
    lines += ["", "## Span validation", "", "| Route | Count |", "|---|---:|"]
    lines += [f"| {key} | {value} |" for key, value in sorted(routes.items())]
    lines += ["", "Non-continuous spans and text entered under a `NO` decision remain in `human_review_note`; they are not presented as evidence spans."]
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"benchmark": str(output), "stats": str(stats_output), "report": str(report_output), "records": len(benchmark), "supported": supported}, ensure_ascii=False))


if __name__ == "__main__":
    main()
