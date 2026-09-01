"""Select valid second-pass entity-identity risks for human review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Validated v3 second-pass JSONL")
    parser.add_argument("--output", required=True)
    parser.add_argument("--supported-only", action="store_true", help="Keep only first-pass ABSTRACT_SUPPORTED rows")
    args = parser.parse_args()
    source, output = ROOT / args.input, ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    selected: list[dict] = []
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            verification = row.get("verification") or {}
            supported = (row.get("layer1_review") or {}).get("support_status") == "ABSTRACT_SUPPORTED"
            if row.get("verification_validation_route") != "VALID" or not verification.get("entity_identity_risk"):
                continue
            if args.supported_only and not supported:
                continue
            selected.append({
                "record_key": row.get("record_key"), "input": row.get("input"),
                "layer1_review": row.get("layer1_review"), "layer2_decision": verification.get("decision"),
                "entity_identity_risk": True, "entity_risk_note": verification.get("entity_risk_note", ""),
                "queue_reason": "SECOND_PASS_ENTITY_IDENTITY_RISK",
            })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"input": str(source), "output": str(output), "selected": len(selected)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
