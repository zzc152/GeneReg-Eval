"""Compare validated Qwen abstract-review outputs with human-review benchmark labels."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/workspace/zzc/GeneReg-Eval")


def metrics(rows: list[dict]) -> dict:
    tp = sum(x["human"] and x["prediction"] for x in rows)
    fp = sum(not x["human"] and x["prediction"] for x in rows)
    tn = sum(not x["human"] and not x["prediction"] for x in rows)
    fn = sum(x["human"] and not x["prediction"] for x in rows)
    total = len(rows)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"records": total, "tp": tp, "fp": fp, "tn": tn, "fn": fn, "accuracy": (tp + tn) / total if total else None, "precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision and recall else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-output", required=True)
    args = parser.parse_args()
    output, report_output = ROOT / args.output, ROOT / args.report_output
    if output.exists() or report_output.exists():
        raise SystemExit("Refusing to overwrite an existing evaluation artifact")
    with (ROOT / args.benchmark).open(encoding="utf-8") as handle:
        human = {x["benchmark_id"]: x for x in (json.loads(line) for line in handle if line.strip())}
    rows, status_counts, route_counts = [], Counter(), Counter()
    with (ROOT / args.model).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            model = json.loads(line)
            sample_id = model["input"].get("sample_id")
            reference = human.get(sample_id)
            if reference is None:
                raise SystemExit(f"No human benchmark record for {sample_id}")
            review = model.get("review", {})
            status, route = review.get("support_status"), model.get("validation_route")
            raw_supported = status == "ABSTRACT_SUPPORTED"
            prediction = raw_supported and route == "VALID"
            status_counts[status] += 1
            route_counts[route] += 1
            rows.append({"benchmark_id": sample_id, "pmid": reference["pmid"], "species": reference["species"], "mor": reference["trrust_mor"], "human": bool(reference["human_abstract_supported"]), "model_status": status, "validation_route": route, "prediction": prediction, "span_validation_route": reference["span_validation_route"], "model_evidence_span": review.get("evidence_span"), "human_evidence_span": reference.get("human_evidence_span")})
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["species"], row["mor"])].append(row)
    summary = {"evaluation_version": "qwen_vs_human_review_benchmark_v1_20260828", "decision_rule": "Model positive = ABSTRACT_SUPPORTED and deterministic validator route VALID; PARTIAL and INSUFFICIENT are negative.", "records": len(rows), "model_status_counts": dict(status_counts), "validator_route_counts": dict(route_counts), "overall": metrics(rows), "by_species_mor": [{"species": k[0], "mor": k[1], **metrics(v)} for k, v in sorted(grouped.items())], "mismatches": [x for x in rows if x["human"] != x["prediction"]], "supported_model_spans": {"model_supported": sum(x["model_status"] == "ABSTRACT_SUPPORTED" for x in rows), "validated_supported": sum(x["prediction"] for x in rows)}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    overall = summary["overall"]
    fmt = lambda value: "n/a" if value is None else f"{value:.1%}"
    lines = ["# Qwen vs human-review benchmark", "", summary["decision_rule"], "", "## Overall", "", f"- Records: {len(rows)}", f"- Model statuses: {dict(status_counts)}", f"- Validator routes: {dict(route_counts)}", f"- Accuracy: {fmt(overall['accuracy'])}", f"- Precision: {fmt(overall['precision'])}", f"- Recall: {fmt(overall['recall'])}", f"- F1: {fmt(overall['f1'])}", f"- Confusion matrix: TP={overall['tp']}, FP={overall['fp']}, TN={overall['tn']}, FN={overall['fn']}", f"- Model ABSTRACT_SUPPORTED: {summary['supported_model_spans']['model_supported']}; validator-valid supported: {summary['supported_model_spans']['validated_supported']}", "", "## By species × TRRUST MoR", "", "| Species | MoR | N | Accuracy | Precision | Recall | F1 |", "|---|---|---:|---:|---:|---:|---:|"]
    lines += [f"| {x['species']} | {x['mor']} | {x['records']} | {fmt(x['accuracy'])} | {fmt(x['precision'])} | {fmt(x['recall'])} | {fmt(x['f1'])} |" for x in summary["by_species_mor"]]
    lines += ["", f"Mismatches requiring qualitative review: {len(summary['mismatches'])}."]
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "report": str(report_output), **overall}, ensure_ascii=False))


if __name__ == "__main__":
    main()
