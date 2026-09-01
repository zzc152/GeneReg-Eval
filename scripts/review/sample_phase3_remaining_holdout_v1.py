"""Create a balanced sample from holdout records not already human reviewed."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def species_of(item: dict) -> str:
    return str(item.get("species") or item.get("stratum", {}).get("species"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--reviewed-human", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats-output", required=True)
    parser.add_argument("--seed", type=int, default=20260829)
    args = parser.parse_args()
    output, stats_path = ROOT / args.output, ROOT / args.stats_output
    if output.exists() or stats_path.exists():
        raise SystemExit("Refusing to overwrite an existing sampling artifact")
    reviewed = {row["record_key"] for row in (json.loads(line) for line in (ROOT / args.reviewed_human).open(encoding="utf-8") if line.strip())}
    remaining = [row for row in (json.loads(line) for line in (ROOT / args.model).open(encoding="utf-8") if line.strip()) if row["record_key"] not in reviewed]
    quotas = {(species, mor): 5 for species in ("human", "mouse") for mor in ("Activation", "Repression", "Unknown")}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in remaining:
        item = row["input"]
        groups[(species_of(item), item["relation"])].append(row)
    rng = random.Random(args.seed)
    selected: list[dict] = []
    for key, quota in quotas.items():
        if len(groups[key]) < quota:
            raise ValueError(f"Insufficient remaining records for {key}: {len(groups[key])} < {quota}")
        selected.extend(rng.sample(groups[key], quota))
    rng.shuffle(selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats = {"sample_version": "phase3_remaining_holdout_second_pass_sample_v1_20260829", "seed": args.seed, "reviewed_excluded": len(reviewed), "remaining_pool": len(remaining), "sample_size": len(selected), "strata": [{"species": k[0], "mor": k[1], "available": len(groups[k]), "sampled": quotas[k]} for k in sorted(quotas)]}
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "stats": str(stats_path), "records": len(selected)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
