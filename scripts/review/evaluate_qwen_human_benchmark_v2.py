"""Evaluate Qwen against benchmark v2, excluding explicitly uncertain labels."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/workspace/zzc/GeneReg-Eval")


def score(rows: list[dict]) -> dict:
    tp = sum(r["human"] and r["pred"] for r in rows); fp = sum(not r["human"] and r["pred"] for r in rows)
    tn = sum(not r["human"] and not r["pred"] for r in rows); fn = sum(r["human"] and not r["pred"] for r in rows)
    precision = tp / (tp + fp) if tp + fp else None; recall = tp / (tp + fn) if tp + fn else None
    return {"records": len(rows), "tp": tp, "fp": fp, "tn": tn, "fn": fn, "accuracy": (tp + tn) / len(rows) if rows else None, "precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision and recall else None}


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--model", required=True); p.add_argument("--benchmark", required=True); p.add_argument("--output", required=True); p.add_argument("--report-output", required=True); a = p.parse_args()
    output, report = ROOT / a.output, ROOT / a.report_output
    if output.exists() or report.exists(): raise SystemExit("Refusing to overwrite an existing evaluation artifact")
    human = {x["benchmark_id"]: x for x in (json.loads(line) for line in (ROOT / a.benchmark).open(encoding="utf-8") if line.strip())}
    rows, excluded, statuses, routes = [], [], Counter(), Counter()
    for line in (ROOT / a.model).open(encoding="utf-8"):
        if not line.strip(): continue
        m = json.loads(line); ref = human[m["input"]["sample_id"]]
        if not ref.get("calibration_eligible", True): excluded.append({"benchmark_id": ref["benchmark_id"], "pmid": ref["pmid"]}); continue
        status, route = m["review"].get("support_status"), m.get("validation_route")
        statuses[status] += 1; routes[route] += 1
        rows.append({"benchmark_id": ref["benchmark_id"], "pmid": ref["pmid"], "species": ref["species"], "mor": ref["trrust_mor"], "human": bool(ref["human_abstract_supported"]), "pred": status == "ABSTRACT_SUPPORTED" and route == "VALID", "model_status": status, "validation_route": route})
    groups = defaultdict(list)
    for row in rows: groups[(row["species"], row["mor"])].append(row)
    overall = score(rows)
    result = {"evaluation_version": "qwen_vs_human_review_benchmark_v2_20260828", "decision_rule": "Positive = ABSTRACT_SUPPORTED plus VALID. PARTIAL/INSUFFICIENT are negative.", "records": len(rows), "excluded_uncertain_records": excluded, "model_status_counts": dict(statuses), "validator_route_counts": dict(routes), "overall": overall, "by_species_mor": [{"species": k[0], "mor": k[1], **score(v)} for k, v in sorted(groups.items())], "mismatches": [r for r in rows if r["human"] != r["pred"]]}
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pct = lambda x: "n/a" if x is None else f"{x:.1%}"
    lines = ["# Qwen vs human-review benchmark v2", "", result["decision_rule"], "", f"- Included records: {len(rows)}", f"- Excluded uncertain: {len(excluded)}", f"- Model statuses: {dict(statuses)}", f"- Validator routes: {dict(routes)}", f"- Accuracy: {pct(overall['accuracy'])}", f"- Precision: {pct(overall['precision'])}", f"- Recall: {pct(overall['recall'])}", f"- F1: {pct(overall['f1'])}", f"- Confusion matrix: TP={overall['tp']}, FP={overall['fp']}, TN={overall['tn']}, FN={overall['fn']}", "", "| Species | MoR | N | Accuracy | Precision | Recall | F1 |", "|---|---|---:|---:|---:|---:|---:|"]
    lines += [f"| {x['species']} | {x['mor']} | {x['records']} | {pct(x['accuracy'])} | {pct(x['precision'])} | {pct(x['recall'])} | {pct(x['f1'])} |" for x in result["by_species_mor"]]
    report.parent.mkdir(parents=True, exist_ok=True); report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "report": str(report), **overall}, ensure_ascii=False))


if __name__ == "__main__": main()
