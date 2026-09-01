"""Paired comparison of two OpenCompass strict-L0 benchmark result sets.

The script compares predictions by the immutable benchmark row order, reports
correctness transitions, an exact two-sided McNemar test, and a paired bootstrap
confidence interval for the accuracy difference (candidate minus baseline).
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def one(value: Any) -> Any:
    return value[0] if isinstance(value, list) and len(value) == 1 else value


def load_predictions(dataset: Path, result: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(dataset)
    details = json.loads(result.read_text(encoding="utf-8"))["details"]
    if len(rows) != len(details):
        raise ValueError(f"row/detail count mismatch for {result}: {len(rows)} != {len(details)}")
    items: list[dict[str, Any]] = []
    for row, detail in zip(rows, details):
        predicted_option = one(detail["parsed"])
        gold_option = one(detail["refr"])
        gold = row[gold_option]
        predicted = row.get(predicted_option, "INVALID")
        items.append(
            {
                "benchmark_id": row["benchmark_id"],
                "pmid": row["pmid"],
                "task": row["task"],
                "gold": gold,
                "prediction": predicted,
                "correct": predicted == gold,
                "question": row["question"],
                "options": {key: row[key] for key in ("A", "B")},
                "gold_option": gold_option,
            }
        )
    return items


def exact_mcnemar_p_value(baseline_correct_candidate_wrong: int, baseline_wrong_candidate_correct: int) -> float:
    """Two-sided exact binomial McNemar p-value under p=0.5."""
    discordant = baseline_correct_candidate_wrong + baseline_wrong_candidate_correct
    if not discordant:
        return 1.0
    lower = min(baseline_correct_candidate_wrong, baseline_wrong_candidate_correct)
    probability = sum(math.comb(discordant, k) for k in range(lower + 1)) / (2**discordant)
    return min(1.0, 2.0 * probability)


def paired_bootstrap_delta(items: list[dict[str, Any]], repetitions: int, seed: int) -> dict[str, float | int]:
    deltas = [int(item["candidate_correct"]) - int(item["baseline_correct"]) for item in items]
    rng = random.Random(seed)
    n = len(deltas)
    samples = [sum(deltas[rng.randrange(n)] for _ in range(n)) / n for _ in range(repetitions)]
    samples.sort()
    return {
        "repetitions": repetitions,
        "seed": seed,
        "point_estimate": sum(deltas) / n,
        "ci_95_percentile_lower": samples[int(0.025 * repetitions)],
        "ci_95_percentile_upper": samples[min(repetitions - 1, math.ceil(0.975 * repetitions) - 1)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--direction-data", required=True, type=Path)
    parser.add_argument("--direction-baseline-result", required=True, type=Path)
    parser.add_argument("--direction-candidate-result", required=True, type=Path)
    parser.add_argument("--presence-data", required=True, type=Path)
    parser.add_argument("--presence-baseline-result", required=True, type=Path)
    parser.add_argument("--presence-candidate-result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--transition-output",
        type=Path,
        help="Optional JSON containing only items whose correctness changes between models.",
    )
    parser.add_argument("--bootstrap-repetitions", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260901)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite: {args.output}")

    pairs: list[dict[str, Any]] = []
    for dataset, baseline_result, candidate_result in (
        (args.direction_data, args.direction_baseline_result, args.direction_candidate_result),
        (args.presence_data, args.presence_baseline_result, args.presence_candidate_result),
    ):
        baseline = load_predictions(dataset, baseline_result)
        candidate = load_predictions(dataset, candidate_result)
        for left, right in zip(baseline, candidate):
            if left["benchmark_id"] != right["benchmark_id"] or left["gold"] != right["gold"]:
                raise ValueError("benchmark identity/gold mismatch between result sets")
            pairs.append({**left, "candidate_prediction": right["prediction"], "candidate_correct": right["correct"], "baseline_correct": left["correct"]})

    transitions = Counter(
        f"7B_{'correct' if row['baseline_correct'] else 'wrong'}__32B_{'correct' if row['candidate_correct'] else 'wrong'}"
        for row in pairs
    )
    by_gold: dict[str, dict[str, int]] = defaultdict(lambda: Counter())
    for row in pairs:
        key = f"7B_{'correct' if row['baseline_correct'] else 'wrong'}__32B_{'correct' if row['candidate_correct'] else 'wrong'}"
        by_gold[row["gold"]][key] += 1
    b = transitions["7B_correct__32B_wrong"]
    c = transitions["7B_wrong__32B_correct"]
    payload = {
        "metric_version": "opencompass_strict_l0_paired_comparison_v1",
        "baseline_model": "Qwen2.5-7B-Instruct",
        "candidate_model": "Qwen2.5-32B-AWQ",
        "total": len(pairs),
        "baseline_correct": sum(row["baseline_correct"] for row in pairs),
        "candidate_correct": sum(row["candidate_correct"] for row in pairs),
        "correctness_transitions": dict(transitions),
        "mcnemar_exact_two_sided": {
            "baseline_correct_candidate_wrong": b,
            "baseline_wrong_candidate_correct": c,
            "discordant_pairs": b + c,
            "p_value": exact_mcnemar_p_value(b, c),
        },
        "paired_bootstrap_accuracy_delta_32B_minus_7B": paired_bootstrap_delta(pairs, args.bootstrap_repetitions, args.seed),
        "correctness_transitions_by_gold_label": {label: dict(counts) for label, counts in sorted(by_gold.items())},
        "paired_items": pairs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.transition_output:
        if args.transition_output.exists():
            raise SystemExit(f"refusing to overwrite: {args.transition_output}")
        changed_items = []
        for row in pairs:
            if row["baseline_correct"] == row["candidate_correct"]:
                continue
            changed_items.append(
                {
                    "transition": "WRONG_TO_CORRECT" if row["candidate_correct"] else "CORRECT_TO_WRONG",
                    "benchmark_id": row["benchmark_id"],
                    "pmid": row["pmid"],
                    "task": row["task"],
                    "question": row["question"],
                    "options": row["options"],
                    "gold_option": row["gold_option"],
                    "gold_label": row["gold"],
                    "qwen25_7b_prediction": row["prediction"],
                    "qwen25_32b_prediction": row["candidate_prediction"],
                }
            )
        transition_payload = {
            "artifact_version": "opencompass_strict_l0_model_transition_cases_v1",
            "baseline_model": "Qwen2.5-7B-Instruct",
            "candidate_model": "Qwen2.5-32B-AWQ",
            "total_changed_items": len(changed_items),
            "wrong_to_correct": sum(item["transition"] == "WRONG_TO_CORRECT" for item in changed_items),
            "correct_to_wrong": sum(item["transition"] == "CORRECT_TO_WRONG" for item in changed_items),
            "items": changed_items,
        }
        args.transition_output.parent.mkdir(parents=True, exist_ok=True)
        args.transition_output.write_text(
            json.dumps(transition_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({key: value for key, value in payload.items() if key != "paired_items"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
