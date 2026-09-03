"""Export OpenCompass MCQ predictions as per-item, fully auditable JSONL.

The OpenCompass prediction files retain the exact rendered chat prompt and raw
model completion.  This exporter binds them back to the frozen benchmark item
so that one line contains the full input, options, raw output, parsed letter,
gold label, and correctness outcome.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def prediction_map(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"prediction file must be an object: {path}")
    return payload


def raw_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def parse_option(value: Any) -> str | None:
    text = raw_text(value)
    if not text:
        return None
    # OpenCompass's multiple-choice evaluator accepts an answer letter followed
    # by its rendered option text (for example ``B. Repression``).  Preserve
    # that behavior in the audit export rather than treating otherwise valid
    # completions as parsing failures.
    match = re.match(r"\s*([AB])(?=\s*(?:[.:：)）,-]|\s|$))", text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else None


def prompt_text(origin_prompt: Any) -> str | None:
    if isinstance(origin_prompt, list):
        return "\n\n".join(
            str(part.get("prompt", "")) for part in origin_prompt if isinstance(part, dict)
        )
    return raw_text(origin_prompt)


def append_task(rows: list[dict[str, Any]], data_path: Path, pred_path: Path, model: str) -> None:
    data, predictions = jsonl(data_path), prediction_map(pred_path)
    if set(predictions) != {str(index) for index in range(len(data))}:
        raise ValueError(f"prediction indices do not match {data_path}: {len(predictions)} predictions for {len(data)} rows")
    for index, item in enumerate(data):
        pred = predictions[str(index)]
        gold_option = item["answer"]
        if pred.get("gold") != gold_option:
            raise ValueError(f"gold option mismatch for {item['benchmark_id']}")
        raw = pred.get("prediction")
        parsed = parse_option(raw)
        rows.append({
            "model": model,
            "benchmark_id": item["benchmark_id"],
            "sample_id": item["sample_id"],
            "pmid": item["pmid"],
            "task": item["task"],
            "full_input": prompt_text(pred.get("origin_prompt")),
            "input_messages": pred.get("origin_prompt"),
            "options": {"A": item["A"], "B": item["B"]},
            "gold_option": gold_option,
            "gold_label": item[gold_option],
            "raw_model_output": raw_text(raw),
            "parsed_option": parsed,
            "parsed_label": item.get(parsed) if parsed else None,
            "is_correct": parsed == gold_option,
            "prediction_source": str(pred_path),
        })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--direction-data", required=True, type=Path)
    parser.add_argument("--presence-data", required=True, type=Path)
    parser.add_argument("--direction-prediction", required=True, type=Path)
    parser.add_argument("--presence-prediction", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stats-output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.stats_output.exists():
        raise SystemExit("refusing to overwrite an audit artifact")
    rows: list[dict[str, Any]] = []
    append_task(rows, args.direction_data, args.direction_prediction, args.model)
    append_task(rows, args.presence_data, args.presence_prediction, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    counts = Counter(row["is_correct"] for row in rows)
    stats = {
        "model": args.model,
        "total": len(rows),
        "correct": counts[True],
        "incorrect": counts[False],
        "accuracy": counts[True] / len(rows) if rows else None,
        "task_counts": dict(Counter(row["task"] for row in rows)),
        "task_accuracy": {
            task: sum(row["is_correct"] for row in rows if row["task"] == task) / sum(1 for row in rows if row["task"] == task)
            for task in sorted({row["task"] for row in rows})
        },
    }
    args.stats_output.parent.mkdir(parents=True, exist_ok=True)
    args.stats_output.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
