"""Deterministically stratify Phase 3 two-layer outputs for human audit."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def load(path: str) -> list[dict]:
    with (ROOT / path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def key(first: dict, second: dict) -> tuple[str, str, str]:
    return (
        str((first.get("review") or {}).get("support_status")),
        str((second.get("verification") or {}).get("decision")),
        "ENTITY_RISK" if (second.get("verification") or {}).get("entity_identity_risk") else "NO_ENTITY_RISK",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-pass", required=True)
    parser.add_argument("--second-pass", required=True, help="Validated v3 second-pass JSONL")
    parser.add_argument("--first-output", required=True)
    parser.add_argument("--second-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--records", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260830)
    args = parser.parse_args()
    first = load(args.first_pass)
    second = {row["record_key"]: row for row in load(args.second_pass)}
    if len(first) != len(second) or any(row["record_key"] not in second for row in first):
        raise ValueError("first/second rows are not one-to-one")
    if not 0 < args.records <= len(first):
        raise ValueError("records must be in 1..population size")
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in first:
        groups[key(row, second[row["record_key"]])].append(row)
    rng = random.Random(args.seed)
    for rows in groups.values():
        rng.shuffle(rows)
    total = len(first)
    quotas: dict[tuple[str, str, str], int] = {}
    fractions: list[tuple[float, tuple[str, str, str]]] = []
    for group_key, rows in groups.items():
        raw = args.records * len(rows) / total
        quotas[group_key] = min(len(rows), int(raw))
        fractions.append((raw - int(raw), group_key))
    remaining = args.records - sum(quotas.values())
    for _, group_key in sorted(fractions, reverse=True):
        if remaining <= 0:
            break
        if quotas[group_key] < len(groups[group_key]):
            quotas[group_key] += 1
            remaining -= 1
    chosen = [row for group_key in sorted(groups) for row in groups[group_key][:quotas[group_key]]]
    rng.shuffle(chosen)
    first_output, second_output, manifest = ROOT / args.first_output, ROOT / args.second_output, ROOT / args.manifest_output
    if any(path.exists() for path in (first_output, second_output, manifest)):
        raise SystemExit("Refusing to overwrite an existing audit sample artifact")
    for path in (first_output, second_output, manifest):
        path.parent.mkdir(parents=True, exist_ok=True)
    with first_output.open("x", encoding="utf-8") as handle:
        for row in chosen:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with second_output.open("x", encoding="utf-8") as handle:
        for row in chosen:
            handle.write(json.dumps(second[row["record_key"]], ensure_ascii=False) + "\n")
    manifest_data = {
        "sample_version": "phase3_two_layer_audit_sample_v1_20260830",
        "seed": args.seed, "population_records": total, "sample_records": len(chosen),
        "strata": [{"layer1_status": item[0], "layer2_decision": item[1], "entity_identity_risk": item[2], "population": len(groups[item]), "sampled": quotas[item]} for item in sorted(groups)],
    }
    manifest.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest_data, ensure_ascii=False))


if __name__ == "__main__":
    main()
