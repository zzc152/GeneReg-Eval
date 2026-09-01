"""Normalize a completed Phase 3 holdout HTML audit without altering its source export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def species_of(item: dict) -> str:
    return str(item.get("species") or item.get("stratum", {}).get("species"))


def supported(value: object) -> bool:
    text = str(value or "").strip().upper()
    if text.startswith("YES"):
        return True
    if text.startswith("NO"):
        return False
    raise ValueError(f"Unrecognized independently_supported value: {value!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="JSON array exported from the human audit page")
    parser.add_argument("--selected", required=True, help="The 50-row selected model-output JSONL")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    audits = json.loads((ROOT / args.source).read_text(encoding="utf-8"))
    selected = [json.loads(line) for line in (ROOT / args.selected).open(encoding="utf-8") if line.strip()]
    if len(audits) != len(selected):
        raise ValueError(f"Source has {len(audits)} records but selected sample has {len(selected)}")
    normalized: list[dict] = []
    for position, (audit, model_row) in enumerate(zip(audits, selected), 1):
        if audit.get("index") != position:
            raise ValueError(f"Expected source index {position}, got {audit.get('index')!r}")
        candidate = audit.get("trrust_candidate") or {}
        item = model_row["input"]
        expected = {"tf": item["tf_mention"], "target": item["object_mention"], "mor": item["relation"]}
        if candidate != expected:
            raise ValueError(f"Candidate mismatch at index {position}: source={candidate!r}, expected={expected!r}")
        human = audit.get("human_audit") or {}
        label = supported(human.get("independently_supported"))
        span = human.get("evidence_span")
        if label and not str(span or "").strip():
            raise ValueError(f"Supported audit lacks an evidence span at index {position}")
        normalized.append({
            "audit_id": f"phase3_holdout_audit_v1_{position:03d}",
            "source_index": position,
            "record_key": model_row["record_key"],
            "pmid": item["pmid"],
            "species": species_of(item),
            "trrust_tf": item["tf_mention"],
            "trrust_target": item["object_mention"],
            "trrust_mor": item["relation"],
            "human_abstract_supported": label,
            "human_evidence_span": span if label else None,
            "human_review_note": human.get("audit_note"),
            "human_support_input": human.get("independently_supported"),
            "label_provenance": "human_review",
            "source_file": Path(args.source).name,
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        for row in normalized:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({
        "output": str(output),
        "records": len(normalized),
        "supported": sum(row["human_abstract_supported"] for row in normalized),
        "not_supported": sum(not row["human_abstract_supported"] for row in normalized),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
