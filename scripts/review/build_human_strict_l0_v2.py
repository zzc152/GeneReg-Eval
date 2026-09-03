"""Build the frozen Human strict L0 v2 release.

This release retains every v1 record and adds the independently sampled,
human-reviewed TRRUST-Unknown reserve.  It is intentionally a new benchmark
version: no v1 file is modified and all input source hashes are recorded.
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
VERSION = "human_strict_l0_v2_20260902"


def resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-release", required=True)
    parser.add_argument("--unknown-release", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    v1_dir, unknown_dir, output_dir = map(resolve, (args.v1_release, args.unknown_release, args.output_dir))
    if output_dir.exists():
        raise SystemExit(f"refusing to overwrite existing release: {output_dir}")
    v1_strict_path = v1_dir / "strict_records.jsonl"
    unknown_strict_path = unknown_dir / "strict_unknown_l0.jsonl"
    v1_articles_path = v1_dir / "sources" / "article_records.jsonl"
    unknown_articles_path = unknown_dir / "sources" / "reserve_manifest.jsonl"
    v1_records, unknown_records = read_jsonl(v1_strict_path), read_jsonl(unknown_strict_path)
    v1_articles, unknown_articles = read_jsonl(v1_articles_path), read_jsonl(unknown_articles_path)

    all_records = v1_records + unknown_records
    for key in ("sample_id", "pmid"):
        values = [row[key] for row in all_records]
        if len(values) != len(set(values)):
            duplicates = sorted(item for item, count in Counter(values).items() if count > 1)
            raise ValueError(f"cross-release duplicate {key}: {duplicates[:10]}")
    article_rows = v1_articles + unknown_articles
    article_by_id = {row["sample_id"]: row for row in article_rows}
    if len(article_by_id) != len(article_rows):
        raise ValueError("duplicate sample_id across article sources")
    strict_ids = {row["sample_id"] for row in all_records}
    missing_articles = sorted(strict_ids - set(article_by_id))
    if missing_articles:
        raise ValueError(f"strict records missing article sources: {missing_articles[:10]}")
    for row in all_records:
        article = article_by_id[row["sample_id"]].get("article")
        if not isinstance(article, dict) or not article.get("title") or not article.get("abstract"):
            raise ValueError(f"missing title/abstract for {row['sample_id']}")
        row["benchmark_id"] = f"{VERSION}:{row['sample_id']}"
        row["benchmark_version"] = VERSION
        row["provenance"] = {
            **(row.get("provenance") or {}),
            "combined_release_version": VERSION,
            "combined_release_component": "v1_holdout" if row in v1_records else "independent_unknown_reserve",
        }
    all_records.sort(key=lambda row: row["sample_id"])
    # v1 keeps article text for its full 400-row review pool; release v2 ships
    # only source articles referenced by its strict scoring records.
    article_rows = [article_by_id[sample_id] for sample_id in strict_ids]
    article_rows.sort(key=lambda row: row["sample_id"])

    output_dir.mkdir(parents=True)
    source_dir = output_dir / "sources"
    source_dir.mkdir()
    write_jsonl(output_dir / "strict_records.jsonl", all_records)
    write_jsonl(source_dir / "article_records.jsonl", article_rows)
    # Keep frozen source material self-contained without mutating old releases.
    for src, name in (
        (v1_strict_path, "v1_strict_records.jsonl"),
        (unknown_strict_path, "unknown_strict_records.jsonl"),
        (v1_dir / "sources" / "reviewed_source.json", "v1_reviewed_source.json"),
        (v1_dir / "sources" / "uncertain_resolved_source.json", "v1_uncertain_resolved_source.json"),
        (unknown_dir / "sources" / "reviewed_source.json", "unknown_reviewed_source.json"),
        (unknown_dir / "sources" / "uncertain_resolved_source.json", "unknown_uncertain_resolved_source.json"),
    ):
        shutil.copy2(src, source_dir / name)
    manifest = {
        "benchmark_version": VERSION,
        "scope": "Human, PubMed title/abstract only, strict L0 classification.",
        "composition": {
            "retained_human_strict_l0_v1_records": len(v1_records),
            "added_independent_trrust_unknown_reserve_records": len(unknown_records),
            "total_records": len(all_records),
            "unique_pmids": len({row["pmid"] for row in all_records}),
        },
        "tasks": dict(Counter(row["l0"]["task"] for row in all_records)),
        "labels": dict(Counter(row["l0"]["gold_label"] for row in all_records)),
        "independence": {
            "checked_cross_component_sample_id_overlap": False,
            "checked_cross_component_pmid_overlap": False,
            "unknown_reserve_policy": "All 200 reserve PMIDs, including 36 excluded from strict scoring, remain permanently excluded from later construction pools.",
        },
        "input_sha256": {
            str(v1_strict_path.relative_to(ROOT)): sha256(v1_strict_path),
            str(unknown_strict_path.relative_to(ROOT)): sha256(unknown_strict_path),
            str(v1_articles_path.relative_to(ROOT)): sha256(v1_articles_path),
            str(unknown_articles_path.relative_to(ROOT)): sha256(unknown_articles_path),
        },
        "model_input_policy": "Models see only title, abstract, and candidate regulator-target query; no TRRUST MoR or human gold label.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "README.md").write_text(
        "# Human strict L0 benchmark v2\n\n"
        "该冻结版本保留 `human_strict_l0_v1_20260901` 的全部 267 条记录，并加入独立抽样、人工审阅的 TRRUST Unknown reserve。"
        "严格集仅包含 `ABSTRACT_SUPPORTED` 与 `ABSTRACT_INSUFFICIENT`；Partial/uncertain 不会被重标为负例。\n\n"
        f"- 总计：{len(all_records)} 条、{len({row['pmid'] for row in all_records})} 个独立 PMID\n"
        f"- 方向题：{manifest['tasks'].get('KNOWN_DIRECTION', 0)} 条\n"
        f"- Unknown 关系存在性题：{manifest['tasks'].get('UNKNOWN_RELATION_PRESENCE', 0)} 条\n"
        "\n运行 OpenCompass 前，使用 `scripts/review/build_opencompass_human_strict_l0_v1.py` 对本目录的 strict 与 article source 物化题目。\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
