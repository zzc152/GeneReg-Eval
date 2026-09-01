"""Evaluate whether a second-pass verifier correctly audits first-pass decisions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def metrics(rows: list[dict], key: str) -> dict:
    tp = sum(row["human"] and row[key] for row in rows)
    fp = sum(not row["human"] and row[key] for row in rows)
    tn = sum(not row["human"] and not row[key] for row in rows)
    fn = sum(row["human"] and not row[key] for row in rows)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "accuracy": (tp + tn) / len(rows) if rows else None, "precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision and recall else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validated-first-pass", required=True)
    parser.add_argument("--verifier", required=True)
    parser.add_argument("--human", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    humans = {row["record_key"]: row for row in (json.loads(line) for line in (ROOT / args.human).open(encoding="utf-8") if line.strip())}
    first = {row["record_key"]: row for row in (json.loads(line) for line in (ROOT / args.validated_first_pass).open(encoding="utf-8") if line.strip())}
    verifier = {row["record_key"]: row for row in (json.loads(line) for line in (ROOT / args.verifier).open(encoding="utf-8") if line.strip())}
    rows = []
    for key, second in verifier.items():
        if key not in first or key not in humans:
            raise ValueError(f"Missing first-pass or human record for {key}")
        one, human = first[key], humans[key]
        verification = second.get("verification")
        schema_ok = second.get("verification_validation_route", "VALID") == "VALID" and isinstance(verification, dict) and verification.get("decision") in {"PASS", "REJECT"}
        base_positive = one["review"].get("support_status") == "ABSTRACT_SUPPORTED" and one.get("validation_route") == "VALID"
        verifier_says_correct = verification.get("decision") == "PASS" if schema_ok else None
        gated_positive = base_positive and schema_ok and verifier_says_correct
        rows.append({
            "record_key": key, "pmid": human["pmid"], "tf": human["trrust_tf"], "target": human["trrust_target"], "mor": human["trrust_mor"],
            "human": bool(human["human_abstract_supported"]), "base_positive": base_positive, "gated_positive": gated_positive,
            "base_status": one["review"].get("support_status"), "base_validation": one.get("validation_route"),
            "schema_ok": schema_ok, "verifier_says_correct": verifier_says_correct, "verifier_decision": verification.get("decision") if schema_ok else None,
        })
    correctness_rows = [row for row in rows if row["schema_ok"]]
    verifier_correctness = sum((row["verifier_says_correct"] == (row["base_positive"] == row["human"])) for row in correctness_rows) / len(correctness_rows) if correctness_rows else None
    result = {"evaluation_version": "phase3_second_pass_verifier_v2_pass_reject", "records": len(rows), "schema_valid": len(correctness_rows), "base": metrics(rows, "base_positive"), "two_layer_gate": metrics(rows, "gated_positive"), "verifier_correctness_accuracy": verifier_correctness, "rows": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(rows), "schema_valid": len(correctness_rows), "base": result["base"], "two_layer_gate": result["two_layer_gate"], "verifier_correctness_accuracy": verifier_correctness}, ensure_ascii=False))


if __name__ == "__main__":
    main()
