"""Create an auditable label-level summary for OpenCompass L0 MCQ results."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def one(value: Any) -> Any:
    return value[0] if isinstance(value, list) and len(value) == 1 else value


def summarize(dataset_path: Path, result_path: Path) -> dict[str, Any]:
    rows = read_jsonl(dataset_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    details = result["details"]
    if len(rows) != len(details):
        raise ValueError(f"row/detail count mismatch: {len(rows)} != {len(details)}")
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    total = correct = invalid = 0
    for row, detail in zip(rows, details):
        predicted_option = one(detail["parsed"])
        gold_option = one(detail["refr"])
        gold = row[gold_option]
        predicted = row.get(predicted_option, "INVALID")
        confusion[gold][predicted] += 1
        total += 1
        correct += predicted == gold
        invalid += predicted == "INVALID"
    labels = sorted({label for label in confusion} | {label for values in confusion.values() for label in values})
    per_label = {}
    for label in labels:
        support = sum(confusion[label].values())
        true_positive = confusion[label][label]
        false_positive = sum(confusion[other][label] for other in labels if other != label)
        per_label[label] = {
            "support": support,
            "correct": true_positive,
            "recall": true_positive / support if support else None,
            "precision": true_positive / (true_positive + false_positive) if true_positive + false_positive else None,
        }
    return {
        "dataset": str(dataset_path),
        "result": str(result_path),
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else None,
        "invalid_option_predictions": invalid,
        "per_label": per_label,
        "confusion": {gold: dict(confusion[gold]) for gold in labels},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--direction-data", required=True, type=Path)
    parser.add_argument("--direction-result", required=True, type=Path)
    parser.add_argument("--presence-data", required=True, type=Path)
    parser.add_argument("--presence-result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite: {args.output}")
    direction = summarize(args.direction_data, args.direction_result)
    presence = summarize(args.presence_data, args.presence_result)
    total = direction["total"] + presence["total"]
    correct = direction["correct"] + presence["correct"]
    payload = {
        "metric_version": "opencompass_strict_l0_summary_v1",
        "overall_micro": {"total": total, "correct": correct, "accuracy": correct / total},
        "tasks": {"known_direction": direction, "unknown_relation_presence": presence},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
