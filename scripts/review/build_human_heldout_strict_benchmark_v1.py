"""Build strict L0/L1 benchmark views from frozen human review sources.

This is deliberately not a partial-support or review benchmark:
* known TRRUST Activation/Repression candidates become a two-class direction
  task (Activation vs Repression), only where the human review is supported
  and gives an explicit direction;
* TRRUST Unknown candidates become a binary relation-exists task, using only
  human ABSTRACT_SUPPORTED vs ABSTRACT_INSUFFICIENT;
* PARTIAL and unresolved/uncertain cases are excluded, never relabelled as
  negative examples.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("GENEREG_EVAL_ROOT", Path(__file__).resolve().parents[2]))
VERSION = "human_heldout_strict_l0_l1_benchmark_v1_20260901"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("records"), list):
        raise ValueError(f"{path} lacks a records list")
    return payload


def l1_complete(row: dict[str, Any]) -> bool:
    return all(row.get(key) for key in (
        "l1_evidence_span", "l1_regulator_mention", "l1_object_mention", "l1_relation"
    )) and row["l1_relation"] in {"Activation", "Repression", "Unknown"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewed", required=True)
    parser.add_argument("--resolved", required=True)
    parser.add_argument("--merged-output", required=True)
    parser.add_argument("--benchmark-output", required=True)
    parser.add_argument("--stats-output", required=True)
    args = parser.parse_args()
    reviewed_path, resolved_path = ROOT / args.reviewed, ROOT / args.resolved
    merged_path, benchmark_path, stats_path = ROOT / args.merged_output, ROOT / args.benchmark_output, ROOT / args.stats_output
    if any(path.exists() for path in (merged_path, benchmark_path, stats_path)):
        raise SystemExit("Refusing to overwrite an existing benchmark artifact")

    reviewed = read_payload(reviewed_path)
    resolved = read_payload(resolved_path)
    by_id = {row["sample_id"]: row for row in reviewed["records"]}
    if len(by_id) != len(reviewed["records"]):
        raise ValueError("duplicate sample_id in reviewed source")
    resolution_ids = set()
    for row in resolved["records"]:
        sample_id = row["sample_id"]
        if sample_id not in by_id:
            raise ValueError(f"resolution references unknown sample_id: {sample_id}")
        by_id[sample_id] = row
        resolution_ids.add(sample_id)
    merged = [by_id[key] for key in sorted(by_id)]

    strict: list[dict[str, Any]] = []
    excluded = Counter()
    for row in merged:
        candidate_relation = row["candidate"]["relation"]
        l0 = row.get("l0_support_status")
        if candidate_relation in {"Activation", "Repression"}:
            if l0 != "ABSTRACT_SUPPORTED":
                excluded[f"known_direction:{l0 or 'UNREVIEWED'}"] += 1
                continue
            direction = row.get("l1_relation")
            if direction not in {"Activation", "Repression"}:
                excluded["known_direction:missing_or_unknown_direction"] += 1
                continue
            task = "KNOWN_DIRECTION"
            gold = direction
        elif candidate_relation == "Unknown":
            if l0 == "ABSTRACT_SUPPORTED":
                task, gold = "UNKNOWN_RELATION_PRESENCE", "REGULATION_PRESENT"
            elif l0 == "ABSTRACT_INSUFFICIENT":
                task, gold = "UNKNOWN_RELATION_PRESENCE", "NO_REGULATION"
            else:
                excluded[f"unknown:{l0 or 'UNREVIEWED'}"] += 1
                continue
        else:
            raise ValueError(f"unexpected candidate relation: {candidate_relation}")
        strict.append({
            "benchmark_id": f"{VERSION}:{row['sample_id']}",
            "benchmark_version": VERSION,
            "sample_id": row["sample_id"],
            "record_key": row["record_key"],
            "pmid": row["pmid"],
            "species": row["species"],
            "candidate": row["candidate"],
            "l0": {
                "task": task,
                "gold_label": gold,
                "answer_options": (["Activation", "Repression"] if task == "KNOWN_DIRECTION" else ["REGULATION_PRESENT", "NO_REGULATION"]),
            },
            "l1": ({
                "eligible": l1_complete(row),
                "evidence_span": row.get("l1_evidence_span"),
                "regulator_mention": row.get("l1_regulator_mention"),
                "object_mention": row.get("l1_object_mention"),
                "relation": row.get("l1_relation"),
                "condition_note": row.get("l1_condition_note"),
            } if gold != "NO_REGULATION" else {"eligible": False}),
            "provenance": {
                "human_review_source": str(reviewed_path.relative_to(ROOT)),
                "uncertain_resolution_source": str(resolved_path.relative_to(ROOT)),
                "resolution_overrode_main_review": row["sample_id"] in resolution_ids,
                "original_l0_support_status": l0,
                "original_l0_note": row.get("l0_note"),
            },
        })

    for path in (merged_path, benchmark_path, stats_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    with merged_path.open("x", encoding="utf-8") as handle:
        for row in merged:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with benchmark_path.open("x", encoding="utf-8") as handle:
        for row in strict:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats = {
        "benchmark_version": VERSION,
        "policy": {
            "known_direction": "Activation vs Repression only; human ABSTRACT_SUPPORTED with explicit human direction.",
            "unknown_relation_presence": "REGULATION_PRESENT vs NO_REGULATION only; human ABSTRACT_SUPPORTED vs ABSTRACT_INSUFFICIENT.",
            "excluded": "ABSTRACT_PARTIAL and remaining uncertain/unreviewed records are excluded, not converted to negatives.",
        },
        "source_review_records": len(reviewed["records"]),
        "resolution_overrides": len(resolution_ids),
        "merged_records": len(merged),
        "strict_records": len(strict),
        "strict_task_counts": dict(Counter(row["l0"]["task"] for row in strict)),
        "strict_label_counts": dict(Counter(row["l0"]["gold_label"] for row in strict)),
        "l1_eligible_records": sum(row["l1"]["eligible"] for row in strict),
        "excluded_counts": dict(sorted(excluded.items())),
        "source_sha256": {
            str(reviewed_path.relative_to(ROOT)): sha256(reviewed_path),
            str(resolved_path.relative_to(ROOT)): sha256(resolved_path),
        },
    }
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"merged": str(merged_path), "benchmark": str(benchmark_path), "stats": str(stats_path), **{key: stats[key] for key in ("strict_records", "strict_task_counts", "strict_label_counts", "l1_eligible_records")}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
