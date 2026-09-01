"""Evaluate a validated Phase 3 holdout extraction against normalized human labels."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def score(rows: list[dict], prediction_key: str) -> dict:
    tp = sum(row["human"] and row[prediction_key] for row in rows)
    fp = sum(not row["human"] and row[prediction_key] for row in rows)
    tn = sum(not row["human"] and not row[prediction_key] for row in rows)
    fn = sum(row["human"] and not row[prediction_key] for row in rows)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {
        "records": len(rows), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": (tp + tn) / len(rows) if rows else None,
        "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision and recall else None,
    }


def error_tags(note: object) -> list[str]:
    text = str(note or "")
    match = re.search(r"Errors?:\s*(.+)$", text, flags=re.I)
    if not match:
        return []
    return [tag.strip().rstrip(".") for tag in match.group(1).split(";") if tag.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--human", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--allow-human-superset", action="store_true", help="Evaluate only model records when human labels include additional records")
    args = parser.parse_args()
    output, report = ROOT / args.output, ROOT / args.report_output
    if output.exists() or report.exists():
        raise SystemExit("Refusing to overwrite an existing evaluation artifact")
    humans = {row["record_key"]: row for row in (json.loads(line) for line in (ROOT / args.human).open(encoding="utf-8") if line.strip())}
    rows: list[dict] = []
    for line in (ROOT / args.model).open(encoding="utf-8"):
        if not line.strip():
            continue
        model = json.loads(line)
        human = humans.pop(model["record_key"], None)
        if human is None:
            continue
        review = model["review"]
        model_supported = review.get("support_status") == "ABSTRACT_SUPPORTED" and model.get("validation_route") == "VALID"
        strict_usable = model_supported and not review.get("review_flag", False)
        rows.append({
            "audit_id": human["audit_id"], "record_key": model["record_key"], "pmid": human["pmid"],
            "species": human["species"], "mor": human["trrust_mor"],
            "tf": human["trrust_tf"], "target": human["trrust_target"],
            "human": bool(human["human_abstract_supported"]), "model_supported": model_supported,
            "strict_usable": strict_usable, "model_status": review.get("support_status"),
            "validation_route": model.get("validation_route"), "review_flag": review.get("review_flag"),
            "model_span": review.get("evidence_span"), "model_note": review.get("review_note"),
            "human_span": human.get("human_evidence_span"), "human_note": human.get("human_review_note"),
        })
    if humans and not args.allow_human_superset:
        raise ValueError(f"Human labels without model records: {len(humans)}")
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["species"], row["mor"])].append(row)
    mismatches = [row for row in rows if row["human"] != row["model_supported"]]
    mismatch_tag_counts = Counter(tag for row in mismatches for tag in error_tags(row["human_note"]))
    result = {
        "evaluation_version": "phase3_holdout_human_audit_v1_20260829",
        "decision_rule": "Model positive = ABSTRACT_SUPPORTED plus validator VALID.",
        "strict_usable_rule": "Model positive plus review_flag=false.",
        "records": len(rows),
        "model_status_counts": dict(Counter(row["model_status"] for row in rows)),
        "validator_route_counts": dict(Counter(row["validation_route"] for row in rows)),
        "review_flag_count": sum(bool(row["review_flag"]) for row in rows),
        "overall": score(rows, "model_supported"),
        "strict_usable_overall": score(rows, "strict_usable"),
        "by_species_mor": [{"species": key[0], "mor": key[1], **score(value, "model_supported")} for key, value in sorted(groups.items())],
        "human_error_tags_on_mismatches": dict(mismatch_tag_counts),
        "mismatches": mismatches,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pct = lambda value: "n/a" if value is None else f"{value:.1%}"
    overall = result["overall"]
    lines = [
        "# Phase 3 holdout: Qwen vs human audit", "", result["decision_rule"],
        f"- Records: {result['records']}", f"- Model statuses: {result['model_status_counts']}",
        f"- Validator routes: {result['validator_route_counts']}", f"- review_flag=true: {result['review_flag_count']}",
        f"- Accuracy: {pct(overall['accuracy'])}", f"- Precision: {pct(overall['precision'])}",
        f"- Recall: {pct(overall['recall'])}", f"- F1: {pct(overall['f1'])}",
        f"- Confusion matrix: TP={overall['tp']}, FP={overall['fp']}, TN={overall['tn']}, FN={overall['fn']}", "",
        "## Mismatch human-note tags", json.dumps(dict(mismatch_tag_counts), ensure_ascii=False), "",
        "## By species and MoR", "", "| Species | MoR | N | Accuracy | Precision | Recall | F1 |", "|---|---|---:|---:|---:|---:|---:|",
    ]
    lines.extend(f"| {item['species']} | {item['mor']} | {item['records']} | {pct(item['accuracy'])} | {pct(item['precision'])} | {pct(item['recall'])} | {pct(item['f1'])} |" for item in result["by_species_mor"])
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "report": str(report), **overall, "mismatches": len(mismatches)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
