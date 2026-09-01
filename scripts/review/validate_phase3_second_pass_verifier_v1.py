"""Validate structural and internal-consistency constraints of verifier sidecars."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")
DECISIONS = {"PASS", "REJECT"}


def errors_for(row: dict) -> list[str]:
    verification = row.get("verification")
    if not isinstance(verification, dict):
        return ["V01: verification must be an object"]
    required = {"decision", "entity_identity_risk", "entity_risk_note"}
    if set(verification) != required:
        return ["V02: verification must contain exactly the required keys"]
    errors: list[str] = []
    if verification["decision"] not in DECISIONS:
        errors.append("V03: decision must be PASS or REJECT")
    if not isinstance(verification["entity_identity_risk"], bool):
        errors.append("V04: entity_identity_risk must be boolean")
    if not isinstance(verification["entity_risk_note"], str):
        errors.append("V05: entity_risk_note must be a string")
    elif not verification["entity_identity_risk"] and verification["entity_risk_note"]:
        errors.append("V06: entity_risk_note must be empty when entity_identity_risk is false")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source, output = ROOT / args.input, ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    routes = {"VALID": 0, "REJECT": 0}
    with source.open(encoding="utf-8") as reader, output.open("x", encoding="utf-8") as writer:
        for line in reader:
            if not line.strip():
                continue
            row = json.loads(line)
            errors = errors_for(row)
            row["verification_validation_route"] = "VALID" if not errors else "REJECT"
            row["verification_validation_errors"] = errors
            routes[row["verification_validation_route"]] += 1
            writer.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"input": str(source), "output": str(output), "routes": routes}, ensure_ascii=False))


if __name__ == "__main__":
    main()
