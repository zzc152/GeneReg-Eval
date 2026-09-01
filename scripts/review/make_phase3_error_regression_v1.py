"""Materialize model inputs for the mismatches in a holdout evaluation report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path("/workspace/zzc/GeneReg-Eval")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    mismatch_keys = {row["record_key"] for row in json.loads((ROOT / args.evaluation).read_text(encoding="utf-8"))["mismatches"]}
    rows = [json.loads(line) for line in (ROOT / args.model).open(encoding="utf-8") if line.strip()]
    selected = [row["input"] for row in rows if row["record_key"] in mismatch_keys]
    if len(selected) != len(mismatch_keys):
        raise ValueError(f"Found {len(selected)} inputs for {len(mismatch_keys)} mismatch keys")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output), "records": len(selected)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
