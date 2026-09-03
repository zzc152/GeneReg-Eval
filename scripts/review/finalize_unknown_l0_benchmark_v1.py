"""Freeze a reviewed TRRUST-Unknown reserve as an independent L0 benchmark.

The main review export contains the complete 200-record workbook.  The
``uncertain_resolved`` export is deliberately shorter: it is an adjudication
patch, not a replacement dataset.  This tool therefore overlays only its
non-empty top-level review fields onto the main export and always retains the
original candidate, article, and sampling provenance from the frozen reserve
manifest.

For a resolved supported row whose ``l1_regulator_mention`` was left blank in
the short form, the field is filled with the candidate (TRRUST) TF mention.
That is a metadata repair only; it does not invent an evidence span, target
mention, direction, or support label.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("GENEREG_EVAL_ROOT", Path(__file__).resolve().parents[2]))
DEFAULT_VERSION = "human_unknown_l0_benchmark_v2_20260902"
PATCHABLE_FIELDS = {
    "l0_support_status", "l0_note", "l1_evidence_span",
    "l1_regulator_mention", "l1_object_mention", "l1_relation",
    "l1_condition_note", "l1_note",
}


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def read_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError(f"{path} must be a JSON object containing records")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def nonempty(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def overlay(base: dict[str, Any], patch: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Apply explicit annotation edits without replacing a complete base row."""
    out = dict(base)
    changed: list[str] = []
    for key in PATCHABLE_FIELDS:
        if key in patch and nonempty(patch[key]):
            if out.get(key) != patch[key]:
                out[key] = patch[key]
                changed.append(key)
    return out, changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reserve-manifest", required=True, help="Frozen 200-row JSONL sampling manifest")
    parser.add_argument("--reviewed", required=True, help="Complete human review export")
    parser.add_argument("--resolved", required=True, help="Short adjudication patch export")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    args = parser.parse_args()

    manifest_path = resolve(args.reserve_manifest)
    reviewed_path = resolve(args.reviewed)
    resolved_path = resolve(args.resolved)
    output_dir = resolve(args.output_dir)
    if output_dir.exists():
        raise SystemExit(f"refusing to overwrite existing output directory: {output_dir}")

    reserve_rows = read_jsonl(manifest_path)
    reserve_by_id = {row["sample_id"]: row for row in reserve_rows}
    if len(reserve_by_id) != len(reserve_rows):
        raise ValueError("duplicate sample_id in reserve manifest")
    reviewed = read_payload(reviewed_path)
    resolved = read_payload(resolved_path)
    reviewed_by_id = {row["sample_id"]: row for row in reviewed["records"]}
    if len(reviewed_by_id) != len(reviewed["records"]):
        raise ValueError("duplicate sample_id in reviewed export")
    if set(reviewed_by_id) != set(reserve_by_id):
        missing = sorted(set(reserve_by_id) - set(reviewed_by_id))
        extra = sorted(set(reviewed_by_id) - set(reserve_by_id))
        raise ValueError(f"reviewed export must cover exactly the reserve sample ids; missing={missing[:5]}, extra={extra[:5]}")

    resolution_by_id = {row["sample_id"]: row for row in resolved["records"]}
    if len(resolution_by_id) != len(resolved["records"]):
        raise ValueError("duplicate sample_id in resolved export")
    unknown_resolution = sorted(set(resolution_by_id) - set(reserve_by_id))
    if unknown_resolution:
        raise ValueError(f"resolution references non-reserve samples: {unknown_resolution[:5]}")

    merged: list[dict[str, Any]] = []
    resolution_changes = Counter()
    tf_fallback_ids: list[str] = []
    for sample_id in sorted(reserve_by_id):
        # The complete review workbook supplies identity/species/L0/L1 fields;
        # the frozen manifest additionally supplies the title and abstract.
        # Keep candidate identity and sampling provenance from the manifest so
        # neither human export can alter the independent sample definition.
        reserve_row = reserve_by_id[sample_id]
        reviewed_row = reviewed_by_id[sample_id]
        if reviewed_row.get("record_key") != reserve_row.get("record_key"):
            raise ValueError(f"record_key mismatch for {sample_id}")
        row = {**reserve_row, **reviewed_row}
        row["article"] = reserve_row.get("article")
        # The reserve sampler's manifest stores article/provenance but does not
        # necessarily repeat its candidate block.  The complete reviewed form
        # does, and that block is the frozen TRRUST candidate for this sample.
        row["candidate"] = reserve_row.get("candidate") or reviewed_row.get("candidate")
        if not isinstance(row["candidate"], dict) or not row["candidate"].get("tf_mention"):
            raise ValueError(f"missing TRRUST candidate/TF for {sample_id}")
        row["provenance"] = reserve_row.get("provenance")
        resolved_row = resolution_by_id.get(sample_id)
        changed: list[str] = []
        if resolved_row is not None:
            row, changed = overlay(row, resolved_row)
            resolution_changes.update(changed)
        candidate = row.get("candidate") or {}
        # User-approved repair for blank TF fields in the short adjudication file.
        if (
            row.get("l0_support_status") == "ABSTRACT_SUPPORTED"
            and not nonempty(row.get("l1_regulator_mention"))
            and nonempty(candidate.get("tf_mention"))
        ):
            row["l1_regulator_mention"] = candidate["tf_mention"]
            tf_fallback_ids.append(sample_id)
        row["provenance"] = {
            **(row.get("provenance") or {}),
            "review_merge_version": args.version,
            "resolution_overrode_main_review": resolved_row is not None,
            "resolution_overridden_fields": changed,
            "tf_mention_fallback_to_trrust_candidate": sample_id in tf_fallback_ids,
        }
        merged.append(row)

    strict: list[dict[str, Any]] = []
    excluded = Counter()
    for row in merged:
        status = row.get("l0_support_status")
        if status == "ABSTRACT_SUPPORTED":
            gold = "REGULATION_PRESENT"
        elif status == "ABSTRACT_INSUFFICIENT":
            gold = "NO_REGULATION"
        else:
            excluded[status or "UNREVIEWED"] += 1
            continue
        strict.append({
            "benchmark_id": f"{args.version}:{row['sample_id']}",
            "benchmark_version": args.version,
            "sample_id": row["sample_id"],
            "record_key": row["record_key"],
            "pmid": row["pmid"],
            "species": row["species"],
            "candidate": row["candidate"],
            "l0": {
                "task": "UNKNOWN_RELATION_PRESENCE",
                "gold_label": gold,
                "answer_options": ["REGULATION_PRESENT", "NO_REGULATION"],
            },
            "l1": {
                "evidence_span": row.get("l1_evidence_span"),
                "regulator_mention": row.get("l1_regulator_mention"),
                "object_mention": row.get("l1_object_mention"),
                "relation": row.get("l1_relation"),
                "condition_note": row.get("l1_condition_note"),
            } if gold == "REGULATION_PRESENT" else {"eligible": False},
            "provenance": row["provenance"],
        })

    output_dir.mkdir(parents=True)
    sources_dir = output_dir / "sources"
    sources_dir.mkdir()
    shutil.copy2(manifest_path, sources_dir / "reserve_manifest.jsonl")
    shutil.copy2(reviewed_path, sources_dir / "reviewed_source.json")
    shutil.copy2(resolved_path, sources_dir / "uncertain_resolved_source.json")
    for filename, rows in (("merged_human_review.jsonl", merged), ("strict_unknown_l0.jsonl", strict)):
        with (output_dir / filename).open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats = {
        "benchmark_version": args.version,
        "scope": "Independent Human TRRUST Unknown candidate reserve; abstract-only L0 relation-presence task.",
        "reservation_policy": "All 200 sampled PMIDs remain permanently excluded from later training, extraction, prompt-development, or benchmark-construction pools.",
        "source_records": len(reserve_rows),
        "unique_pmids": len({row["pmid"] for row in reserve_rows}),
        "resolution_patch_records": len(resolution_by_id),
        "resolution_field_overrides": dict(sorted(resolution_changes.items())),
        "tf_mention_fallback_to_trrust_candidate_count": len(tf_fallback_ids),
        "tf_mention_fallback_sample_ids": tf_fallback_ids,
        "l0_status_counts": dict(Counter(row.get("l0_support_status") or "UNREVIEWED" for row in merged)),
        "strict_records": len(strict),
        "strict_label_counts": dict(Counter(row["l0"]["gold_label"] for row in strict)),
        "excluded_l0_status_counts": dict(sorted(excluded.items())),
        "source_sha256": {
            "reserve_manifest": sha256(manifest_path),
            "reviewed": sha256(reviewed_path),
            "resolved": sha256(resolved_path),
        },
    }
    (output_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), **{key: stats[key] for key in ("source_records", "resolution_patch_records", "tf_mention_fallback_to_trrust_candidate_count", "strict_records", "strict_label_counts")}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
