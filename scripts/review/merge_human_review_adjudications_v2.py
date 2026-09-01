"""Create benchmark v2 by applying later human disagreement adjudications to v1."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path("/workspace/zzc/GeneReg-Eval")

# The written note for this lone BOTH_DEFENSIBLE record explicitly resolves it
# as PPI rather than transcriptional regulation; the later note is authoritative.
NOTE_RESOLVED_MODEL_CORRECT = {"both_mentioned_support_audit_v1_049"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-v1", required=True)
    parser.add_argument("--adjudications", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stats-output", required=True)
    args = parser.parse_args()
    output, stats_output = ROOT / args.output, ROOT / args.stats_output
    if output.exists() or stats_output.exists():
        raise SystemExit("Refusing to overwrite an existing benchmark v2 artifact")
    with (ROOT / args.benchmark_v1).open(encoding="utf-8") as handle:
        base = [json.loads(line) for line in handle if line.strip()]
    adjudications = {x["sample_id"]: x for x in json.loads((ROOT / args.adjudications).read_text(encoding="utf-8"))}
    with (ROOT / args.model).open(encoding="utf-8") as handle:
        model = {x["input"]["sample_id"]: x for x in (json.loads(line) for line in handle if line.strip())}
    merged, sources = [], Counter()
    for row in base:
        item = dict(row)
        sample_id = row["benchmark_id"]
        adjudication = adjudications.get(sample_id)
        item["benchmark_version"] = "human_review_benchmark_v2_20260828"
        item["human_review_v1_abstract_supported"] = row["human_abstract_supported"]
        item["adjudication"] = adjudication.get("adjudication") if adjudication else None
        item["adjudication_note"] = adjudication.get("note") if adjudication and adjudication.get("note") else None
        item["calibration_eligible"] = True
        if not adjudication:
            source = "HUMAN_REVIEW_V1_UNCHANGED"
        elif adjudication["adjudication"] == "HUMAN_CORRECT":
            source = "LATER_ADJUDICATION_HUMAN_CORRECT"
        elif adjudication["adjudication"] == "MODEL_CORRECT" or sample_id in NOTE_RESOLVED_MODEL_CORRECT:
            model_row = model.get(sample_id)
            if model_row is None:
                raise SystemExit(f"Missing model output for adjudication {sample_id}")
            item["human_abstract_supported"] = model_row["review"].get("support_status") == "ABSTRACT_SUPPORTED" and model_row.get("validation_route") == "VALID"
            source = "LATER_ADJUDICATION_MODEL_CORRECT" if adjudication["adjudication"] == "MODEL_CORRECT" else "LATER_NOTE_RESOLVED_MODEL_CORRECT"
        elif adjudication["adjudication"] == "UNCERTAIN":
            item["human_abstract_supported"] = None
            item["calibration_eligible"] = False
            source = "LATER_ADJUDICATION_UNCERTAIN"
        else:
            raise SystemExit(f"Unhandled adjudication for {sample_id}: {adjudication['adjudication']}")
        item["label_source"] = source
        sources[source] += 1
        merged.append(item)
    stats = {
        "benchmark_version": "human_review_benchmark_v2_20260828",
        "records": len(merged), "calibration_eligible": sum(x["calibration_eligible"] for x in merged),
        "not_calibration_eligible": sum(not x["calibration_eligible"] for x in merged),
        "supported": sum(x["human_abstract_supported"] is True for x in merged),
        "not_supported": sum(x["human_abstract_supported"] is False for x in merged),
        "label_source_counts": dict(sources),
        "policy": "Later human adjudication/note overrides v1. UNCERTAIN adjudications are preserved but excluded from calibration metrics.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in merged) + "\n", encoding="utf-8")
    stats_output.parent.mkdir(parents=True, exist_ok=True)
    stats_output.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
